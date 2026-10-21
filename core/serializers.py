from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .comunas_chile import COMUNAS_POR_REGION
from .forms import _validar_email_unico
from .models import REGION_CHOICES, Condominio, Membresia, Torre, Unidad

_REGIONES_VALIDAS = {codigo for codigo, _ in REGION_CHOICES}
_COMUNAS_VALIDAS = {comuna for comunas in COMUNAS_POR_REGION.values() for comuna in comunas}


class CondominioResumenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Condominio
        fields = ["id", "nombre", "plan", "puede_operar"]


class TorreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Torre
        fields = ["id", "nombre"]


class UnidadResumenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unidad
        fields = ["id", "numero"]


class UnidadSerializer(serializers.ModelSerializer):
    """Crear/listar unidades del condominio activo -- misma validación de
    Unidad.clean() (la torre tiene que pertenecer al mismo condominio),
    que un ModelSerializer no corre sola."""

    class Meta:
        model = Unidad
        fields = ["id", "numero", "calle", "torre", "alicuota"]

    def validate(self, attrs):
        torre = attrs.get("torre")
        numero = attrs.get("numero")
        if torre is not None:
            from .permissions import condominio_de_la_api

            condominio = condominio_de_la_api(self.context["request"])
            if torre.condominio_id != condominio.pk:
                raise serializers.ValidationError({"torre": "Esa torre pertenece a otro condominio."})
            # UniqueConstraint(condominio, torre, numero) -- sin este chequeo,
            # un duplicado explota con IntegrityError (500) en vez de un 400
            # que la app pueda mostrar. Con torre=None la restricción no
            # aplica entre sí (NULL != NULL en SQL), por eso solo hace falta
            # acá adentro.
            existe = Unidad.objects.filter(condominio=condominio, torre=torre, numero=numero)
            if self.instance is not None:
                existe = existe.exclude(pk=self.instance.pk)
            if existe.exists():
                raise serializers.ValidationError({"numero": "Ya existe una unidad con ese número en esa torre."})
        return attrs


class DirectorioMiembroSerializer(serializers.Serializer):
    """Directorio simple -- solo nombre y block/depto, igual que
    DirectorioVecinosView (core/views.py). A propósito NO es un
    ModelSerializer: el shape (torre/unidad aplanados, calle+numero
    combinados) no calza 1:1 con ningún modelo."""

    nombre = serializers.SerializerMethodField()
    torre = serializers.CharField(source="unidad.torre.nombre", read_only=True, default=None)
    unidad = serializers.SerializerMethodField()

    def get_nombre(self, obj):
        return obj.user.get_full_name() or "Vecino/a"

    def get_unidad(self, obj):
        if obj.unidad_id is None:
            return None
        if obj.unidad.calle:
            return f"{obj.unidad.calle} {obj.unidad.numero}"
        return obj.unidad.numero


class MembresiaListSerializer(serializers.ModelSerializer):
    """Listado de miembros del condominio activo -- equivalente a
    MiembroListView del panel web (nombre, rol, unidad)."""

    nombre = serializers.SerializerMethodField()
    rol_display = serializers.CharField(source="get_rol_display", read_only=True)
    unidad_numero = serializers.CharField(source="unidad.numero", read_only=True, default=None)
    unidad_torre = serializers.CharField(source="unidad.torre.nombre", read_only=True, default=None)

    class Meta:
        model = Membresia
        fields = ["id", "nombre", "rol", "rol_display", "unidad_numero", "unidad_torre"]

    def get_nombre(self, obj):
        return obj.user.get_full_name() or obj.user.username


class MembresiaSerializer(serializers.ModelSerializer):
    condominio = CondominioResumenSerializer(read_only=True)
    unidad = UnidadResumenSerializer(read_only=True)
    nombre = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = Membresia
        fields = ["rol", "condominio", "unidad", "nombre", "telefono"]


class CondominioEdicionSerializer(serializers.ModelSerializer):
    """Ver/editar el condominio ya creado -- mismos campos que
    CondominioForm (panel web /mi-condominio/), con la misma validación
    cruzada región/comuna (ver RegionComunaMixin.clean())."""

    class Meta:
        model = Condominio
        fields = [
            "nombre", "etiqueta_organizacion", "direccion", "comuna", "region", "datos_transferencia",
            "etiqueta_torre", "etiqueta_unidad", "genero_unidad",
        ]

    def validate_region(self, region):
        if region and region not in _REGIONES_VALIDAS:
            raise serializers.ValidationError("Esa región no existe.")
        return region

    def validate_comuna(self, comuna):
        if comuna and comuna not in _COMUNAS_VALIDAS:
            raise serializers.ValidationError("Esa comuna no existe.")
        return comuna

    def validate(self, attrs):
        region = attrs.get("region", getattr(self.instance, "region", ""))
        comuna = attrs.get("comuna", getattr(self.instance, "comuna", ""))
        if region and comuna and comuna not in COMUNAS_POR_REGION.get(region, []):
            raise serializers.ValidationError({"comuna": "Esa comuna no pertenece a la región elegida."})
        return attrs


class MiPerfilSerializer(serializers.ModelSerializer):
    """Editar los propios datos -- mismos campos y misma validación de email
    único que MiPerfilForm (panel web), para que ambos caminos se comporten
    igual. `telefono` vive en Membresia, no en User -- igual que
    MiPerfilForm, se agrega como campo extra y se guarda a mano en
    update()."""

    telefono = serializers.CharField(required=False, allow_blank=True, max_length=30)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "telefono"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        membresia = getattr(instance, "membresia", None)
        data["telefono"] = membresia.telefono if membresia else ""
        return data

    def validate_email(self, email):
        if not email:
            return email
        try:
            return _validar_email_unico(email, excluir_user_id=self.instance.pk if self.instance else None)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message)

    def validate_telefono(self, telefono):
        # Devquad (is_staff, sin Membresia propia) también usa este
        # endpoint para editar nombre/apellido/email -- sin esto, un
        # PATCH con telefono se aceptaba (200) y el valor se perdía en
        # silencio (no hay Membresia donde guardarlo).
        if getattr(self.instance, "membresia", None) is None:
            raise serializers.ValidationError("Tu cuenta no tiene membresía a ningún condominio.")
        return telefono

    def update(self, instance, validated_data):
        telefono = validated_data.pop("telefono", None)
        user = super().update(instance, validated_data)
        if telefono is not None:
            membresia = getattr(user, "membresia", None)
            if membresia is not None:
                membresia.telefono = telefono
                membresia.save(update_fields=["telefono"])
        return user


class CambiarContrasenaSerializer(serializers.Serializer):
    """Mismas reglas que MiCambiarContrasenaForm (panel web, un
    PasswordChangeForm estándar de Django): exige la contraseña actual,
    valida la nueva con las mismas reglas de Django (largo mínimo, no común,
    no solo números, no muy parecida al resto de los datos del usuario)."""

    password_actual = serializers.CharField(write_only=True)
    password_nueva1 = serializers.CharField(write_only=True)
    password_nueva2 = serializers.CharField(write_only=True)

    def validate_password_actual(self, password):
        if not self.context["request"].user.check_password(password):
            raise serializers.ValidationError("La contraseña actual no es correcta.")
        return password

    def validate(self, attrs):
        if attrs["password_nueva1"] != attrs["password_nueva2"]:
            raise serializers.ValidationError("Las contraseñas nuevas no coinciden.")
        try:
            validate_password(attrs["password_nueva1"], user=self.context["request"].user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password_nueva1": list(error.messages)})
        return attrs

    def save(self):
        user = self.context["request"].user
        user.set_password(self.validated_data["password_nueva1"])
        user.save(update_fields=["password"])
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Igual al login estándar de simplejwt, pero además devuelve la membresía
    del usuario en el mismo response -- evita que la app tenga que hacer un
    segundo request a /auth/me/ apenas inicia sesión."""

    def validate(self, attrs):
        data = super().validate(attrs)
        membresia = getattr(self.user, "membresia", None)
        data["membresia"] = MembresiaSerializer(membresia).data if membresia else None
        return data

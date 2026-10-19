from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .comunas_chile import COMUNAS_POR_REGION
from .forms import _validar_email_unico
from .models import Condominio, Membresia, Torre, Unidad


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
        if torre is not None:
            from .permissions import condominio_de_la_api

            condominio = condominio_de_la_api(self.context["request"])
            if torre.condominio_id != condominio.pk:
                raise serializers.ValidationError({"torre": "Esa torre pertenece a otro condominio."})
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


class MembresiaSerializer(serializers.ModelSerializer):
    condominio = CondominioResumenSerializer(read_only=True)
    unidad = UnidadResumenSerializer(read_only=True)
    nombre = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = Membresia
        fields = ["rol", "condominio", "unidad", "nombre"]


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

    def validate(self, attrs):
        region = attrs.get("region", getattr(self.instance, "region", ""))
        comuna = attrs.get("comuna", getattr(self.instance, "comuna", ""))
        if region and comuna and comuna not in COMUNAS_POR_REGION.get(region, []):
            raise serializers.ValidationError({"comuna": "Esa comuna no pertenece a la región elegida."})
        return attrs


class MiPerfilSerializer(serializers.ModelSerializer):
    """Editar los propios datos -- mismos campos y misma validación de email
    único que MiPerfilForm (panel web), para que ambos caminos se comporten
    igual."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def validate_email(self, email):
        if not email:
            return email
        try:
            return _validar_email_unico(email, excluir_user_id=self.instance.pk if self.instance else None)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message)


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

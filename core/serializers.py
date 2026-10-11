from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .forms import _validar_email_unico
from .models import Condominio, Membresia, Unidad


class CondominioResumenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Condominio
        fields = ["id", "nombre", "plan", "puede_operar"]


class UnidadResumenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unidad
        fields = ["id", "numero"]


class MembresiaSerializer(serializers.ModelSerializer):
    condominio = CondominioResumenSerializer(read_only=True)
    unidad = UnidadResumenSerializer(read_only=True)
    nombre = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = Membresia
        fields = ["rol", "condominio", "unidad", "nombre"]


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
            raise serializers.ValidationError({"password_nueva2": "Las contraseñas nuevas no coinciden."})
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

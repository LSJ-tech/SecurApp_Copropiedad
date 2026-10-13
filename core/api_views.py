from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import CambiarContrasenaSerializer, CustomTokenObtainPairSerializer, MembresiaSerializer, MiPerfilSerializer


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class LogoutView(APIView):
    """Invalida el refresh token (requiere el blacklist app de simplejwt)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=inline_serializer("LogoutRequest", {"refresh": serializers.CharField()}),
        responses={205: None},
    )
    def post(self, request):
        try:
            RefreshToken(request.data["refresh"]).blacklist()
        except (KeyError, TokenError):
            return Response({"detail": "refresh token inválido o ausente."}, status=400)
        return Response(status=205)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=MembresiaSerializer)
    def get(self, request):
        membresia = getattr(request.user, "membresia", None)
        if membresia is None:
            return Response({"detail": "Este usuario no tiene una membresía a ningún condominio."}, status=409)
        return Response(MembresiaSerializer(membresia).data)

    @extend_schema(request=MiPerfilSerializer, responses=MiPerfilSerializer)
    def patch(self, request):
        """Editar nombre/apellido/email -- mismos campos y misma validación
        de email único que MiPerfilView en el panel web."""
        serializer = MiPerfilSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CambiarContrasenaView(APIView):
    """Mismas reglas que MiCambiarContrasenaView en el panel web -- exige la
    contraseña actual, valida la nueva con las reglas estándar de Django."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=CambiarContrasenaSerializer, responses={204: None})
    def post(self, request):
        serializer = CambiarContrasenaSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=204)

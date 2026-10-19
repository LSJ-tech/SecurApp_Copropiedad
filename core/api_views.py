from django.db.models.functions import Length
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Condominio, Membresia
from .permissions import EsDevquad, EsDevquadODelegado, TieneCondominioActivo, condominio_de_la_api
from .serializers import (
    CambiarContrasenaSerializer,
    CondominioResumenSerializer,
    CustomTokenObtainPairSerializer,
    DirectorioMiembroSerializer,
    MembresiaSerializer,
    MiPerfilSerializer,
)


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


class DevquadCondominiosApiView(APIView):
    """Lista todos los condominios/juntas de vecinos -- para que devquad
    elija en cuál operar desde la app móvil (ver DevquadEntrarCondominioApiView).
    Equivalente a DevquadCondominiosView del panel web."""

    permission_classes = [IsAuthenticated, EsDevquad]

    @extend_schema(responses=CondominioResumenSerializer(many=True))
    def get(self, request):
        condominios = Condominio.objects.all().order_by("nombre")
        return Response(CondominioResumenSerializer(condominios, many=True).data)


class DevquadEntrarCondominioApiView(APIView):
    """Marca un condominio como el activo para devquad en la app móvil --
    como la app no comparte la sesión del panel web (ver
    condominio_activo_devquad en core/mixins.py), en vez de guardar nada en
    sesión reemite el login completo (access+refresh) con el condominio
    elegido embebido como claim ("condominio_id") en ambos tokens, para que
    sobreviva a un /auth/refresh/ posterior (ver condominio_de_la_api en
    core/permissions.py). El refresh que se recibe se blacklistea, mismo
    mecanismo que ya usa LogoutView -- no deja dos refresh tokens vivos
    para la misma sesión de devquad."""

    permission_classes = [IsAuthenticated, EsDevquad]

    @extend_schema(
        request=inline_serializer("EntrarCondominioRequest", {"refresh": serializers.CharField()}),
        responses=inline_serializer(
            "EntrarCondominioResponse",
            {"access": serializers.CharField(), "refresh": serializers.CharField(), "condominio": CondominioResumenSerializer()},
        ),
    )
    def post(self, request, pk):
        condominio = get_object_or_404(Condominio, pk=pk)
        try:
            RefreshToken(request.data["refresh"]).blacklist()
        except (KeyError, TokenError):
            return Response({"detail": "refresh token inválido o ausente."}, status=400)

        refresh = RefreshToken.for_user(request.user)
        refresh["condominio_id"] = condominio.pk
        refresh.access_token["condominio_id"] = condominio.pk
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "condominio": CondominioResumenSerializer(condominio).data,
        })


class DirectorioView(APIView):
    """Nombre y block/depto de cada miembro del condominio activo -- igual
    que DirectorioVecinosView del panel web. A propósito NO usa
    TieneCondominioActivo solo: un residente no tiene acceso (decisión de
    producto), solo delegado y devquad -- ver EsDevquadODelegado."""

    permission_classes = [IsAuthenticated, EsDevquadODelegado, TieneCondominioActivo]

    @extend_schema(responses=DirectorioMiembroSerializer(many=True))
    def get(self, request):
        condominio = condominio_de_la_api(request)
        qs = (
            Membresia.objects.filter(condominio=condominio)
            .select_related("user", "unidad", "unidad__torre")
            .annotate(_torre_len=Length("unidad__torre__nombre"), _num_len=Length("unidad__numero"))
            .order_by("_torre_len", "unidad__torre__nombre", "_num_len", "unidad__numero", "user__last_name")
        )
        return Response(DirectorioMiembroSerializer(qs, many=True).data)


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

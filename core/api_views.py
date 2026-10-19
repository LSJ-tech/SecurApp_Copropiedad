from django.db import transaction
from django.db.models.functions import Length
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import mixins, serializers, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from django.contrib.auth.models import User
from django.utils import timezone

from rest_framework.decorators import action

from .forms import CrearMiembroForm, MoverMiembroForm, RegistroResidenteForm
from .models import Condominio, Membresia, Torre, Unidad
from .permissions import CondominioQuerysetMixin, EsDevquad, EsDevquadODelegado, TieneCondominioActivo, condominio_de_la_api
from .serializers import (
    CambiarContrasenaSerializer,
    CondominioEdicionSerializer,
    CondominioResumenSerializer,
    CustomTokenObtainPairSerializer,
    DirectorioMiembroSerializer,
    MembresiaListSerializer,
    MembresiaSerializer,
    MiPerfilSerializer,
    TorreSerializer,
    UnidadSerializer,
)
from .usuarios import generar_codigo_invitacion, generar_password_temporal, generar_username
from .views import _contexto_invitacion, enviar_correo_bienvenida


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
    elegido embebido como claim ("condominio_id") en el refresh -- el
    access que se devuelve sale de ESE refresh (refresh.access_token copia
    su payload), así que ya lo hereda, y un /auth/refresh/ posterior
    también lo hereda del mismo refresh (ver condominio_de_la_api en
    core/permissions.py). El refresh que se recibe se blacklistea, mismo
    mecanismo que ya usa LogoutView -- no deja dos refresh tokens vivos
    para la misma sesión de devquad. Se exige además que ese refresh sea
    del propio usuario autenticado (nunca de otro)."""

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
            token_recibido = RefreshToken(request.data["refresh"])
        except (KeyError, TokenError):
            return Response({"detail": "refresh token inválido o ausente."}, status=400)
        # No basta con estar autenticado -- sin este chequeo, cualquier
        # devquad podría blacklistear el refresh de OTRO usuario mandándolo
        # en el body, desconectándolo sin haber hecho nada.
        if str(token_recibido["user_id"]) != str(request.user.pk):
            return Response({"detail": "Ese refresh token no te pertenece."}, status=400)
        token_recibido.blacklist()

        refresh = RefreshToken.for_user(request.user)
        refresh["condominio_id"] = condominio.pk
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


class CondominioView(APIView):
    """Ver/editar el condominio activo -- equivalente a CondominioUpdateView
    del panel web (sin la parte de QR/invitación, ver InvitacionView)."""

    permission_classes = [IsAuthenticated, EsDevquad, TieneCondominioActivo]

    @extend_schema(responses=CondominioEdicionSerializer)
    def get(self, request):
        return Response(CondominioEdicionSerializer(condominio_de_la_api(request)).data)

    @extend_schema(request=CondominioEdicionSerializer, responses=CondominioEdicionSerializer)
    def patch(self, request):
        serializer = CondominioEdicionSerializer(condominio_de_la_api(request), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class RegenerarTokenApiView(APIView):
    """Regenera el token de autoregistro -- equivalente a
    RegenerarTokenResidentesView del panel web (invalida el link/QR
    anterior)."""

    permission_classes = [IsAuthenticated, EsDevquad, TieneCondominioActivo]

    @extend_schema(responses=inline_serializer("RegenerarTokenResponse", {"token_registro_residentes": serializers.CharField()}))
    def post(self, request):
        condominio = condominio_de_la_api(request)
        condominio.token_registro_residentes = generar_codigo_invitacion()
        condominio.save(update_fields=["token_registro_residentes"])
        return Response({"token_registro_residentes": condominio.token_registro_residentes})


class InvitacionView(APIView):
    """Link/mensaje de autoregistro para compartir -- equivalente a
    CompartirInvitacionView del panel web (_contexto_invitacion ya arma el
    dict con "link_autoregistro"/"mensaje_whatsapp_invitacion")."""

    permission_classes = [IsAuthenticated, TieneCondominioActivo]

    def get(self, request):
        return Response(_contexto_invitacion(request, condominio_de_la_api(request)))


class RegistroPublicoView(APIView):
    """Autoregistro público de residente -- equivalente a
    RegistroResidenteView del panel web, pero sin sesión: devuelve tokens
    JWT en vez de loguear por cookie, para que la app móvil pueda seguir
    autenticada apenas se crea la cuenta."""

    permission_classes = []
    authentication_classes = []

    def get(self, request, token):
        condominio = get_object_or_404(Condominio, token_registro_residentes=token)
        torres = Torre.objects.filter(condominio=condominio).annotate(_len=Length("nombre")).order_by("_len", "nombre")
        unidades = Unidad.objects.filter(condominio=condominio).select_related("torre").annotate(
            _len=Length("numero"),
        ).order_by("torre_id", "_len", "numero")
        return Response({
            "condominio": {
                "nombre": condominio.nombre,
                "etiqueta_organizacion": condominio.etiqueta_organizacion,
                "etiqueta_torre": condominio.etiqueta_torre,
                "etiqueta_unidad": condominio.etiqueta_unidad,
                "genero_unidad": condominio.genero_unidad,
            },
            "torres": [{"id": t.pk, "nombre": t.nombre} for t in torres],
            "unidades": [{"id": u.pk, "numero": u.numero, "torre_id": u.torre_id, "calle": u.calle} for u in unidades],
            "modo_casas": not torres.exists(),
        })

    def post(self, request, token):
        condominio = get_object_or_404(Condominio, token_registro_residentes=token)
        form = RegistroResidenteForm(data=request.data, condominio=condominio)
        if not form.is_valid():
            return Response(form.errors, status=400)
        datos = form.cleaned_data
        username = generar_username(datos["nombre"], datos["apellido"])
        with transaction.atomic():
            user = User.objects.create_user(
                username=username, password=datos["password1"], email=datos.get("email", ""),
                first_name=datos["nombre"], last_name=datos["apellido"],
            )
            membresia = Membresia.objects.create(
                user=user, condominio=condominio, unidad=datos["unidad"], rol="residente",
                terminos_aceptados_en=timezone.now(),
            )
        if user.email:
            enviar_correo_bienvenida(user, condominio)
        refresh = RefreshToken.for_user(user)
        return Response({
            "username": username,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "membresia": MembresiaSerializer(membresia).data,
        }, status=201)


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


class TorreViewSet(CondominioQuerysetMixin, viewsets.ModelViewSet):
    """Listar/crear torres del condominio activo -- equivalente a
    TorreListView/TorreCreateView del panel web."""

    queryset = Torre.objects.all()
    serializer_class = TorreSerializer
    permission_classes = [IsAuthenticated, EsDevquad, TieneCondominioActivo]
    http_method_names = ["get", "post", "head", "options"]

    def perform_create(self, serializer):
        serializer.save(condominio=condominio_de_la_api(self.request))


class PaginacionEstandar(PageNumberPagination):
    """Paginación local a los recursos con volumen real (unidades,
    miembros) -- el proyecto no tiene DEFAULT_PAGINATION_CLASS global
    (Alertas/Avisos nunca paginaron), así que no se toca su forma de
    respuesta."""

    page_size = 50


class UnidadViewSet(CondominioQuerysetMixin, viewsets.ModelViewSet):
    """Listar/crear unidades del condominio activo -- equivalente a
    UnidadListView/UnidadCreateView del panel web."""

    queryset = Unidad.objects.select_related("torre")
    serializer_class = UnidadSerializer
    permission_classes = [IsAuthenticated, EsDevquad, TieneCondominioActivo]
    http_method_names = ["get", "post", "head", "options"]
    pagination_class = PaginacionEstandar

    def get_queryset(self):
        # Meta.ordering=["numero"] es orden de texto ("10" antes que "2") --
        # mismo criterio de orden natural que ya usa UnidadListView del
        # panel web, para que la app no muestre un orden distinto.
        return super().get_queryset().annotate(
            _torre_len=Length("torre__nombre"), _num_len=Length("numero"),
        ).order_by("_torre_len", "torre__nombre", "_num_len", "numero")

    def perform_create(self, serializer):
        serializer.save(condominio=condominio_de_la_api(self.request))


class MembresiaViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    """Listar/crear miembros del condominio activo -- equivalente a
    MiembroListView/CrearMiembroView del panel web. create() reusa
    CrearMiembroForm directo (en vez de un serializer aparte) porque el
    shape de entrada/salida no es el modelo Membresia 1:1: genera usuario
    y contraseña temporal, igual que la vista HTML."""

    serializer_class = MembresiaListSerializer
    permission_classes = [IsAuthenticated, EsDevquad, TieneCondominioActivo]
    pagination_class = PaginacionEstandar

    def get_queryset(self):
        condominio = condominio_de_la_api(self.request)
        return (
            Membresia.objects.filter(condominio=condominio)
            .select_related("user", "unidad", "unidad__torre")
            .annotate(_torre_len=Length("unidad__torre__nombre"), _num_len=Length("unidad__numero"))
            .order_by("rol", "_torre_len", "unidad__torre__nombre", "_num_len", "unidad__numero", "user__last_name")
        )

    def create(self, request, *args, **kwargs):
        condominio = condominio_de_la_api(request)
        form = CrearMiembroForm(data=request.data, condominio=condominio)
        if not form.is_valid():
            return Response(form.errors, status=400)
        datos = form.cleaned_data
        username = generar_username(datos["nombre"], datos["apellido"])
        password = generar_password_temporal()
        with transaction.atomic():
            user = User.objects.create_user(
                username=username, password=password,
                first_name=datos["nombre"], last_name=datos["apellido"], email=datos.get("email", ""),
            )
            membresia = Membresia.objects.create(
                user=user, condominio=condominio, rol=datos["rol"], unidad=datos.get("unidad"),
            )
        if user.email:
            enviar_correo_bienvenida(user, condominio)
        return Response({"id": membresia.pk, "username": username, "password_temporal": password}, status=201)

    @action(detail=True, methods=["patch"])
    def mover(self, request, pk=None):
        """Cambia una Membresia ya existente a otro condominio + unidad --
        equivalente a MoverMiembroView del panel web. Reusa MoverMiembroForm
        tal cual (misma validación: la unidad destino tiene que pertenecer
        al condominio destino elegido)."""
        condominio = condominio_de_la_api(request)
        miembro = get_object_or_404(Membresia, pk=pk, condominio=condominio)
        form = MoverMiembroForm(data=request.data, condominio_actual=condominio)
        if not form.is_valid():
            return Response(form.errors, status=400)
        with transaction.atomic():
            miembro.condominio = form.cleaned_data["condominio_destino"]
            miembro.unidad = form.cleaned_data["unidad_destino"]
            miembro.save(update_fields=["condominio", "unidad"])
        return Response(MembresiaListSerializer(miembro).data)

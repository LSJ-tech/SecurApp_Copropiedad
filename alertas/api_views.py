from datetime import timedelta

from django.db.models import Count, F, Q
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from rest_framework.exceptions import PermissionDenied

from core.permissions import CondominioQuerysetMixin, TieneCondominioActivo, condominio_de_la_api

from .models import NUMEROS_NACIONALES, Alerta, AlertaLectura, NumeroEmergencia
from .serializers import AlertaSerializer, NumeroEmergenciaSerializer
from .services import notificar_alerta, notificar_alerta_resuelta


class AlertaViewSet(CondominioQuerysetMixin, viewsets.ModelViewSet):
    """No hereda el filtro estricto de CondominioQuerysetMixin (ver
    get_queryset) -- las alertas, a diferencia del resto de la API, también
    incluyen las de los condominios_vecinos del propio condominio (ver
    Condominio.ids_red_alertas): es la única excepción deliberada al
    aislamiento multi-tenant, y solo para esto.

    Crear una alerta sigue exigiendo una Membresia real (autor no admite
    null -- una alerta de pánico siempre la dispara una persona concreta
    del condominio, nunca devquad "en nombre de nadie"): ver perform_create.
    Ver/resolver sí las puede operar devquad (resuelta_por sí admite null)."""

    queryset = Alerta.objects.select_related(
        "autor__user", "autor__unidad", "resuelta_por__user", "resuelta_por__unidad"
    ).annotate(
        # Re-acotado a la membresía-del-lector-con-su-condominio-ACTUAL:
        # si esa Membresia se mudó de condominio después de dejar la
        # lectura, esa lectura vieja ya no debe sumar (ver
        # AlertaSerializer.get_visto_por_count).
        visto_por_count_anotado=Count(
            "lecturas", filter=Q(lecturas__membresia__condominio_id=F("condominio_id"))
        )
    )
    serializer_class = AlertaSerializer
    permission_classes = [IsAuthenticated, TieneCondominioActivo]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        condominio = condominio_de_la_api(self.request)
        ids_red = condominio.ids_red_alertas
        qs = self.queryset.filter(condominio_id__in=ids_red)
        estado = self.request.query_params.get("estado")
        if estado == "recientes":
            hace_24h = timezone.now() - timedelta(hours=24)
            qs = qs.exclude(estado="activa").filter(fecha_creacion__gte=hace_24h)[:5]
        elif estado:
            qs = qs.filter(estado=estado)
        return qs

    def perform_create(self, serializer):
        membresia = getattr(self.request.user, "membresia", None)
        if membresia is None:
            raise PermissionDenied("Crear una alerta requiere ser residente/delegado de un condominio.")
        alerta = serializer.save(condominio=membresia.condominio, autor=membresia)
        notificar_alerta(alerta)

    @action(detail=True, methods=["patch"], permission_classes=[IsAuthenticated, TieneCondominioActivo])
    def resolver(self, request, pk=None):
        alerta = self.get_object()
        estado = request.data.get("estado", "resuelta")
        if estado not in ("resuelta", "falsa_alarma"):
            return Response({"detail": "estado inválido."}, status=400)
        alerta.estado = estado
        alerta.resuelta_por = getattr(request.user, "membresia", None)
        alerta.fecha_resolucion = timezone.now()
        alerta.save()
        notificar_alerta_resuelta(alerta)
        return Response(self.get_serializer(alerta).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, TieneCondominioActivo])
    def marcar_visto(self, request, pk=None):
        alerta = self.get_object()
        membresia = getattr(request.user, "membresia", None)
        if membresia is not None and membresia.condominio_id == alerta.condominio_id:
            _, creada = AlertaLectura.objects.get_or_create(alerta=alerta, membresia=membresia)
            if creada:
                # La anotación de visto_por_count_anotado se calculó al
                # traer `alerta` con get_object(), antes de esta lectura
                # nueva -- hay que volver a traerla para que el conteo la
                # incluya.
                alerta = self.get_queryset().get(pk=alerta.pk)
        return Response(self.get_serializer(alerta).data)


class NumeroEmergenciaViewSet(CondominioQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    """Equivalente de NumeroEmergenciaListView (alertas/views.py) para la
    app móvil -- de solo lectura, cualquier residente/delegado con
    condominio activo."""

    queryset = NumeroEmergencia.objects.all()
    serializer_class = NumeroEmergenciaSerializer
    permission_classes = [IsAuthenticated, TieneCondominioActivo]
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        condominio = condominio_de_la_api(self.request)
        if condominio is not None:
            for categoria, nombre, telefono in NUMEROS_NACIONALES:
                NumeroEmergencia.objects.get_or_create(
                    condominio=condominio, nombre=nombre, defaults={"categoria": categoria, "telefono": telefono},
                )
        return super().get_queryset()

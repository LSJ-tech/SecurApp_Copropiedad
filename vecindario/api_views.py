import pygeohash as pgh
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import PRECISION_GEOHASH, AlertaCiudadana
from .permissions import TienePerfilGeografico
from .serializers import AlertaCiudadanaSerializer
from .services import notificar_alerta_ciudadana, vecinos_geohash


class AlertaCiudadanaViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet,
):
    """Igual que alertas.api_views.AlertaViewSet, pero para la red vecinal
    geográfica -- el queryset se acota por geohash del barrio (celda +
    vecinas) en vez de por condominio.

    A propósito NO incluye UpdateModelMixin (sin PATCH/PUT genérico): acá
    el "barrio" es gente sin verificar dentro de un radio de ~5km, no
    vecinos vetados de un condominio -- un PATCH genérico dejaría que
    cualquiera reescriba tipo/mensaje/lat/lng de la alerta de otro, no
    solo marcarla resuelta. La única forma de cambiar una alerta es la
    acción resolver() de abajo, que solo toca estado/resuelta_por/fecha."""

    serializer_class = AlertaCiudadanaSerializer
    permission_classes = [IsAuthenticated, TienePerfilGeografico]

    def get_queryset(self):
        perfil = self.request.user.perfil_geografico
        geohashes = vecinos_geohash(perfil.geohash)
        qs = AlertaCiudadana.objects.filter(autor__geohash__in=geohashes).select_related("autor__user", "resuelta_por__user")
        estado = self.request.query_params.get("estado")
        if estado:
            qs = qs.filter(estado=estado)
        return qs

    def perform_create(self, serializer):
        perfil = self.request.user.perfil_geografico
        lat, lng = serializer.validated_data["lat"], serializer.validated_data["lng"]
        geohash_momento = pgh.encode(float(lat), float(lng), precision=PRECISION_GEOHASH)
        alerta = serializer.save(autor=perfil, geohash_momento=geohash_momento)
        notificar_alerta_ciudadana(alerta)

    @action(detail=True, methods=["patch"], permission_classes=[IsAuthenticated, TienePerfilGeografico])
    def resolver(self, request, pk=None):
        alerta = self.get_object()
        estado = request.data.get("estado", "resuelta")
        if estado not in ("resuelta", "falsa_alarma"):
            return Response({"detail": "estado inválido."}, status=400)
        alerta.estado = estado
        alerta.resuelta_por = request.user.perfil_geografico
        alerta.fecha_resolucion = timezone.now()
        alerta.save()
        return Response(AlertaCiudadanaSerializer(alerta).data)

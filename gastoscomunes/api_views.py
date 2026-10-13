from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from core.permissions import TieneMembresia

from .models import CuotaUnidad
from .serializers import CuotaUnidadSerializer


class CuotaUnidadViewSet(viewsets.ReadOnlyModelViewSet):
    """Fase 1: solo lectura -- el pago se marca manual desde el panel web,
    sin Mercado Pago online todavía (ver plan, sección de pagos)."""

    queryset = CuotaUnidad.objects.all()  # drf-spectacular infiere el tipo del pk de acá, ver get_queryset
    serializer_class = CuotaUnidadSerializer
    permission_classes = [IsAuthenticated, TieneMembresia]

    def get_queryset(self):
        membresia = self.request.user.membresia
        qs = CuotaUnidad.objects.filter(gasto_comun__condominio_id=membresia.condominio_id).select_related("gasto_comun", "unidad")
        if membresia.rol == "residente":
            qs = qs.filter(unidad_id=membresia.unidad_id)
        return qs

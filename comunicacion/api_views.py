from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import (
    CondominioQuerysetMixin,
    EsDirectivaAdministracionODelegado,
    EsDirectivaOAdministracion,
    TieneMembresia,
)

from .models import Aviso, AvisoLectura
from .serializers import AvisoSerializer
from .services import notificar_aviso


class AvisoViewSet(CondominioQuerysetMixin, viewsets.ModelViewSet):
    queryset = Aviso.objects.select_related("autor__user", "torre")
    serializer_class = AvisoSerializer
    permission_classes = [IsAuthenticated, TieneMembresia]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), EsDirectivaAdministracionODelegado()]
        if self.action == "destroy":
            return [IsAuthenticated(), EsDirectivaOAdministracion()]
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        membresia = self.request.user.membresia
        if membresia.rol in ("directiva", "administracion", "conserje"):
            return qs  # gestionan/moderan todo el condominio, no solo su torre
        # Un residente/delegado ve lo de todo el condominio (torre=None) más
        # lo que se publicó solo para SU torre -- nunca lo de otra torre.
        torre_id = membresia.unidad.torre_id if membresia.unidad_id else None
        return qs.filter(Q(torre__isnull=True) | Q(torre_id=torre_id))

    def perform_create(self, serializer):
        membresia = self.request.user.membresia
        torre = membresia.unidad.torre if (membresia.rol == "delegado" and membresia.unidad_id) else None
        aviso = serializer.save(condominio=membresia.condominio, autor=membresia, torre=torre)
        notificar_aviso(aviso)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, TieneMembresia])
    def marcar_leido(self, request, pk=None):
        aviso = self.get_object()
        AvisoLectura.objects.get_or_create(aviso=aviso, membresia=request.user.membresia)
        return Response(AvisoSerializer(aviso, context={"request": request}).data)

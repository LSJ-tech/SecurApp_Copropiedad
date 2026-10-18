from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import (
    CondominioQuerysetMixin,
    EsDevquad,
    EsDevquadODelegado,
    TieneCondominioActivo,
    condominio_de_la_api,
)

from .models import Aviso, AvisoLectura
from .serializers import AvisoSerializer
from .services import notificar_aviso


class AvisoViewSet(CondominioQuerysetMixin, viewsets.ModelViewSet):
    queryset = Aviso.objects.select_related("autor__user", "torre")
    serializer_class = AvisoSerializer
    permission_classes = [IsAuthenticated, TieneCondominioActivo]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), EsDevquadODelegado()]
        if self.action == "destroy":
            return [IsAuthenticated(), EsDevquad()]
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        membresia = getattr(self.request.user, "membresia", None)
        if membresia is None or self.request.user.is_staff:
            return qs  # devquad gestiona/modera todo el condominio, no solo su torre
        # Un residente/delegado ve lo de todo el condominio (torre=None) más
        # lo que se publicó solo para SU torre -- nunca lo de otra torre.
        torre_id = membresia.unidad.torre_id if membresia.unidad_id else None
        return qs.filter(Q(torre__isnull=True) | Q(torre_id=torre_id))

    def perform_create(self, serializer):
        condominio = condominio_de_la_api(self.request)
        membresia = getattr(self.request.user, "membresia", None)
        torre = membresia.unidad.torre if (membresia and membresia.rol == "delegado" and membresia.unidad_id) else None
        aviso = serializer.save(condominio=condominio, autor=membresia, torre=torre)
        notificar_aviso(aviso)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, TieneCondominioActivo])
    def marcar_leido(self, request, pk=None):
        """Devquad no tiene Membresia -- no hay "leído por" que registrarle
        (AvisoLectura.membresia es obligatoria), simplemente no se guarda
        nada para esa cuenta, sin que la acción falle."""
        aviso = self.get_object()
        membresia = getattr(request.user, "membresia", None)
        if membresia is not None:
            AvisoLectura.objects.get_or_create(aviso=aviso, membresia=membresia)
        return Response(AvisoSerializer(aviso, context={"request": request}).data)

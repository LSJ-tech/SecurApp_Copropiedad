from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import CondominioQuerysetMixin, EsAutorODirectivaOAdministracion, EsDirectivaOAdministracion, TieneMembresia

from .models import Aviso, AvisoLectura, Publicacion
from .serializers import AvisoSerializer, PublicacionSerializer


class AvisoViewSet(CondominioQuerysetMixin, viewsets.ModelViewSet):
    queryset = Aviso.objects.select_related("autor__user")
    serializer_class = AvisoSerializer
    permission_classes = [IsAuthenticated, TieneMembresia]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ("create", "destroy"):
            return [IsAuthenticated(), EsDirectivaOAdministracion()]
        return super().get_permissions()

    def perform_create(self, serializer):
        membresia = self.request.user.membresia
        serializer.save(condominio=membresia.condominio, autor=membresia)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, TieneMembresia])
    def marcar_leido(self, request, pk=None):
        aviso = self.get_object()
        AvisoLectura.objects.get_or_create(aviso=aviso, membresia=request.user.membresia)
        return Response(AvisoSerializer(aviso, context={"request": request}).data)


class PublicacionViewSet(CondominioQuerysetMixin, viewsets.ModelViewSet):
    """Muro de vecinos: a diferencia de Aviso, cualquier miembro puede
    publicar -- solo borrar está restringido (ver EsAutorODirectivaOAdministracion)."""

    queryset = Publicacion.objects.select_related("autor__user", "autor__unidad__torre")
    serializer_class = PublicacionSerializer
    permission_classes = [IsAuthenticated, TieneMembresia]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_permissions(self):
        if self.action == "destroy":
            return [IsAuthenticated(), EsAutorODirectivaOAdministracion()]
        return super().get_permissions()

    def perform_create(self, serializer):
        membresia = self.request.user.membresia
        serializer.save(condominio=membresia.condominio, autor=membresia)

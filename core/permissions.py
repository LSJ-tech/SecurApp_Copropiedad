from rest_framework.permissions import BasePermission


def _rol(request):
    membresia = getattr(request.user, "membresia", None)
    return membresia.rol if membresia else None


class EsDirectivaOAdministracion(BasePermission):
    def has_permission(self, request, view):
        return _rol(request) in ("directiva", "administracion")


class TieneMembresia(BasePermission):
    """Cualquier rol, siempre que tenga una Membresia asociada (aislamiento básico de tenant)."""

    def has_permission(self, request, view):
        return getattr(request.user, "membresia", None) is not None


class CondominioQuerysetMixin:
    """Mezclar en cualquier ViewSet/APIView de la API: filtra siempre por el
    condominio de la membresía del usuario logueado. Sin esto, un endpoint
    filtraría solo por pk y rompería el aislamiento entre condominios -- el
    error más común al empezar con DRF multi-tenant.
    """

    permission_classes_base = [TieneMembresia]

    def get_queryset(self):
        condominio_id = self.request.user.membresia.condominio_id
        return super().get_queryset().filter(condominio_id=condominio_id)

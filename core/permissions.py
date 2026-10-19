from rest_framework.permissions import BasePermission

from .mixins import condominio_activo_devquad


def _rol(request):
    membresia = getattr(request.user, "membresia", None)
    return membresia.rol if membresia else None


def condominio_de_la_api(request):
    """Condominio resuelto para esta request -- vía la Membresia de
    residente/delegado, o vía el condominio activo en sesión de un devquad
    (is_staff, sin Membresia propia -- ver DevquadCondominiosView y
    condominio_activo_devquad en core/mixins.py, mismo mecanismo que usa
    CondominioRequiredMixin del lado de las vistas normales). None si no
    corresponde a ninguno de los dos casos."""
    from .models import Condominio

    membresia = getattr(request.user, "membresia", None)
    if membresia is not None:
        return membresia.condominio
    if request.user.is_authenticated and request.user.is_staff:
        token = getattr(request, "auth", None)
        condominio_id = token.get("condominio_id") if token is not None else None
        if condominio_id is not None:
            return Condominio.objects.filter(pk=condominio_id).first()
        return condominio_activo_devquad(request)
    return None


class EsDevquad(BasePermission):
    """Reemplaza a EsDirectivaOAdministracion -- devquad ya no es un rol de
    Membresia (ver ROL_CHOICES), es quien opera la plataforma entera
    (User.is_staff), igual que SoloStaffMixin del lado de las vistas
    normales."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_staff)


class EsDevquadODelegado(BasePermission):
    """Reemplaza a EsDirectivaAdministracionODelegado: devquad publica a
    todo el condominio, un delegado solo a su propia torre (ver
    AvisoViewSet.perform_create)."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_staff) or _rol(request) == "delegado"


class TieneCondominioActivo(BasePermission):
    """Reemplaza a TieneMembresia (nombre ya no preciso: devquad nunca
    tiene Membresia). Cualquiera con un condominio resuelto -- residente/
    delegado vía su Membresia, o devquad vía el condominio activo en
    sesión (ver condominio_de_la_api)."""

    def has_permission(self, request, view):
        return condominio_de_la_api(request) is not None


class CondominioQuerysetMixin:
    """Mezclar en cualquier ViewSet/APIView de la API: filtra siempre por el
    condominio resuelto para el usuario logueado (ver condominio_de_la_api).
    Sin esto, un endpoint filtraría solo por pk y rompería el aislamiento
    entre condominios -- el error más común al empezar con DRF multi-tenant.
    """

    permission_classes_base = [TieneCondominioActivo]

    def get_queryset(self):
        condominio = condominio_de_la_api(self.request)
        return super().get_queryset().filter(condominio_id=condominio.pk if condominio else None)

from rest_framework.permissions import BasePermission


class TienePerfilGeografico(BasePermission):
    """Igual que core.permissions.TieneMembresia, pero para la red vecinal
    geográfica -- cualquier usuario con PerfilGeografico, sin exigir Membresia."""

    def has_permission(self, request, view):
        return getattr(request.user, "perfil_geografico", None) is not None

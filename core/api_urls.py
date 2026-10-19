from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import api_views

router = DefaultRouter()
router.register("torres", api_views.TorreViewSet, basename="torre")
router.register("unidades", api_views.UnidadViewSet, basename="unidad")
router.register("miembros", api_views.MembresiaViewSet, basename="membresia")

urlpatterns = [
    path("auth/login/", api_views.CustomTokenObtainPairView.as_view(), name="api-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="api-refresh"),
    path("auth/logout/", api_views.LogoutView.as_view(), name="api-logout"),
    path("auth/me/", api_views.MeView.as_view(), name="api-me"),
    path("auth/cambiar-contrasena/", api_views.CambiarContrasenaView.as_view(), name="api-cambiar-contrasena"),
    path("devquad/condominios/", api_views.DevquadCondominiosApiView.as_view(), name="api-devquad-condominios"),
    path("devquad/condominios/<int:pk>/entrar/", api_views.DevquadEntrarCondominioApiView.as_view(), name="api-devquad-entrar-condominio"),
    path("directorio/", api_views.DirectorioView.as_view(), name="api-directorio"),
    path("condominio/", api_views.CondominioView.as_view(), name="api-condominio"),
    path("condominio/regenerar-token/", api_views.RegenerarTokenApiView.as_view(), name="api-regenerar-token"),
    path("invitacion/", api_views.InvitacionView.as_view(), name="api-invitacion"),
    path("registro/<str:token>/", api_views.RegistroPublicoView.as_view(), name="api-registro"),
] + router.urls

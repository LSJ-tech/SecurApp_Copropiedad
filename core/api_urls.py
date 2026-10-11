from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import api_views

urlpatterns = [
    path("auth/login/", api_views.CustomTokenObtainPairView.as_view(), name="api-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="api-refresh"),
    path("auth/logout/", api_views.LogoutView.as_view(), name="api-logout"),
    path("auth/me/", api_views.MeView.as_view(), name="api-me"),
    path("auth/cambiar-contrasena/", api_views.CambiarContrasenaView.as_view(), name="api-cambiar-contrasena"),
]

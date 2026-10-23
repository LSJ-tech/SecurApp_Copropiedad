from django.urls import path

from . import api_views

urlpatterns = [
    path("pagos/mi-donacion/", api_views.MiDonacionApiView.as_view(), name="api-mi-donacion"),
    path("pagos/donar/", api_views.DonarApiView.as_view(), name="api-donar"),
    path("pagos/donar/cancelar/", api_views.CancelarDonacionApiView.as_view(), name="api-donar-cancelar"),
]

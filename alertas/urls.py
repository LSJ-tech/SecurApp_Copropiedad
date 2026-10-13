from django.urls import path

from . import views

urlpatterns = [
    path("alertas/historial/", views.AlertaHistorialView.as_view(), name="alertas-historial"),
    path("alertas/numeros-emergencia/", views.NumeroEmergenciaListView.as_view(), name="numeros-emergencia"),
    path("alertas/numeros-emergencia/agregar/", views.NumeroEmergenciaCreateView.as_view(), name="numero-emergencia-crear"),
    path("alertas/numeros-emergencia/<int:pk>/eliminar/", views.EliminarNumeroEmergenciaView.as_view(), name="numero-emergencia-eliminar"),
]

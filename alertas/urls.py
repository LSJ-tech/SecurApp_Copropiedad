from django.urls import path

from . import views

urlpatterns = [
    path("alertas/historial/", views.AlertaHistorialView.as_view(), name="alertas-historial"),
    path("alertas/numeros-emergencia/", views.NumeroEmergenciaListView.as_view(), name="numeros-emergencia"),
    path("alertas/numeros-emergencia/agregar/", views.NumeroEmergenciaCreateView.as_view(), name="numero-emergencia-crear"),
    path("alertas/numeros-emergencia/<int:pk>/eliminar/", views.EliminarNumeroEmergenciaView.as_view(), name="numero-emergencia-eliminar"),
    path("alertas/numeros-emergencia/proponer/", views.ProponerNumeroEmergenciaView.as_view(), name="numero-emergencia-proponer"),
    path("alertas/numeros-emergencia/propuestas/<int:pk>/aprobar/", views.AprobarPropuestaNumeroEmergenciaView.as_view(), name="propuesta-numero-emergencia-aprobar"),
    path("alertas/numeros-emergencia/propuestas/<int:pk>/rechazar/", views.RechazarPropuestaNumeroEmergenciaView.as_view(), name="propuesta-numero-emergencia-rechazar"),
]

from django.urls import path

from . import views

urlpatterns = [
    path("donar/", views.DonarView.as_view(), name="donar"),
    path("donar/cancelar/", views.CancelarDonacionRecurrenteView.as_view(), name="cancelar-donacion"),
    path("pago/resultado/", views.PagoResultadoView.as_view(), name="pago-resultado"),
    path("mis-donaciones/", views.MisDonacionesView.as_view(), name="mis-donaciones"),
    path("pago/webhook/", views.WebhookMercadoPagoView.as_view(), name="pago-webhook"),
]

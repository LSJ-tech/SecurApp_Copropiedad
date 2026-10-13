from django.urls import path

from . import views

urlpatterns = [
    path("donar/", views.DonarView.as_view(), name="donar"),
    path("donar/cancelar/", views.CancelarDonacionRecurrenteView.as_view(), name="cancelar-donacion"),
    path("suscripcion/pagar/", views.SuscripcionPagarView.as_view(), name="pagar-suscripcion"),
    path("suscripcion/cancelar/", views.CancelarSuscripcionRecurrenteView.as_view(), name="cancelar-suscripcion"),
    path("pago/resultado/", views.PagoResultadoView.as_view(), name="pago-resultado"),
    path("pago/webhook/", views.WebhookMercadoPagoView.as_view(), name="pago-webhook"),
]

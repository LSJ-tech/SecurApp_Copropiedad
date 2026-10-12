from django.urls import path

from . import views

urlpatterns = [
    path("gastos-comunes/", views.GastoComunListView.as_view(), name="gastos-comunes-list"),
    path("gastos-comunes/nuevo/", views.GastoComunCreateView.as_view(), name="gastos-comunes-crear"),
    path("gastos-comunes/datos-transferencia/", views.DatosTransferenciaUpdateView.as_view(), name="datos-transferencia"),
    path("gastos-comunes/<int:gasto_pk>/cuotas/", views.CuotaListView.as_view(), name="gastos-comunes-cuotas"),
    path("gastos-comunes/<int:gasto_pk>/cuotas/exportar.xlsx", views.CuotasExportarExcelView.as_view(), name="gastos-comunes-cuotas-excel"),
    path("gastos-comunes/<int:gasto_pk>/cuotas/exportar.pdf", views.CuotasExportarPDFView.as_view(), name="gastos-comunes-cuotas-pdf"),
    path("cuotas/<int:pk>/marcar-pagada/", views.MarcarCuotaPagadaView.as_view(), name="cuota-marcar-pagada"),
    path("cuotas/<int:pk>/boucher/", views.BoucherPDFView.as_view(), name="cuota-boucher"),
    path("mis-cuotas/", views.MisCuotasView.as_view(), name="mis-cuotas"),
]

from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.filters.admin import AutocompleteSelectFilter
from unfold.decorators import display

from .models import CuotaUnidad, GastoComun


class CuotaUnidadInline(TabularInline):
    """estado se muestra como badge de solo lectura -- marcar una cuota
    como pagada es trabajo del panel web (MarcarCuotaPagadaView), no de
    este admin interno, así que no hace falta que sea editable acá."""

    model = CuotaUnidad
    extra = 0
    fields = ["unidad", "monto", "estado_badge", "fecha_pago"]
    readonly_fields = ["estado_badge"]

    @display(description="Estado", label={"pendiente": "warning", "pagado": "success", "vencido": "danger"})
    def estado_badge(self, obj):
        return obj.estado, obj.get_estado_display()


@admin.register(GastoComun)
class GastoComunAdmin(ModelAdmin):
    list_display = ["condominio", "periodo", "monto_total", "fecha_vencimiento"]
    list_filter = [("condominio", AutocompleteSelectFilter)]
    list_filter_submit = True
    inlines = [CuotaUnidadInline]

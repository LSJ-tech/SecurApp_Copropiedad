from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import AutocompleteSelectFilter

from .models import Afp, Empleado, Liquidacion, ParametrosPeriodo, TramoImpuestoUnico


@admin.register(Afp)
class AfpAdmin(ModelAdmin):
    list_display = ["nombre", "tasa_total_pct"]


@admin.register(TramoImpuestoUnico)
class TramoImpuestoUnicoAdmin(ModelAdmin):
    list_display = ["desde_utm", "hasta_utm", "tasa_pct", "rebaja_utm"]


@admin.register(ParametrosPeriodo)
class ParametrosPeriodoAdmin(ModelAdmin):
    list_display = ["periodo", "valor_utm", "valor_uf", "ingreso_minimo_mensual", "tope_imponible_afp_salud_uf", "tope_imponible_cesantia_uf"]


@admin.register(Empleado)
class EmpleadoAdmin(ModelAdmin):
    list_display = ["nombre", "condominio", "cargo", "tipo_contrato", "sueldo_base", "activo"]
    list_filter = [("condominio", AutocompleteSelectFilter), "activo", "tipo_contrato"]
    list_filter_submit = True
    search_fields = ["nombre", "rut"]
    list_select_related = ["condominio"]


@admin.register(Liquidacion)
class LiquidacionAdmin(ModelAdmin):
    list_display = ["empleado", "periodo", "liquido_a_pagar", "fecha_generacion"]
    list_filter = [("empleado__condominio", AutocompleteSelectFilter), "periodo"]
    list_filter_submit = True
    readonly_fields = [f.name for f in Liquidacion._meta.fields if f.name not in ("id",)]
    list_select_related = ["empleado"]

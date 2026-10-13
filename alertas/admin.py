from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import AutocompleteSelectFilter
from unfold.decorators import display

from .models import Alerta, NumeroEmergencia, PropuestaNumeroEmergencia


@admin.register(Alerta)
class AlertaAdmin(ModelAdmin):
    list_display = ["condominio", "tipo_badge", "estado_badge", "autor", "fecha_creacion"]
    list_filter = [("condominio", AutocompleteSelectFilter), "tipo", "estado"]
    list_filter_submit = True

    @display(description="Tipo", ordering="tipo", label={"robo": "danger", "incendio": "danger", "accidente": "warning", "emergencia_medica": "danger", "persona_extrana": "warning", "fuga_gas": "danger", "fuga_agua": "warning", "atrapado_ascensor": "warning", "objeto_sospechoso": "warning", "rina_disturbio": "danger", "otro": "info", "prueba": "info"})
    def tipo_badge(self, obj):
        return obj.tipo, obj.get_tipo_display()

    @display(description="Estado", ordering="estado", label={"activa": "danger", "resuelta": "success", "falsa_alarma": "warning", "auto_cerrada": "info"})
    def estado_badge(self, obj):
        return obj.estado, obj.get_estado_display()


@admin.register(NumeroEmergencia)
class NumeroEmergenciaAdmin(ModelAdmin):
    list_display = ["nombre", "telefono", "categoria", "condominio"]
    list_filter = [("condominio", AutocompleteSelectFilter), "categoria"]
    list_filter_submit = True
    list_select_related = ["condominio"]


@admin.register(PropuestaNumeroEmergencia)
class PropuestaNumeroEmergenciaAdmin(ModelAdmin):
    list_display = ["nombre", "telefono", "categoria", "estado_badge", "condominio", "autor", "fecha_creacion"]
    list_filter = [("condominio", AutocompleteSelectFilter), "categoria", "estado"]
    list_filter_submit = True
    list_select_related = ["condominio", "autor__user"]

    @display(description="Estado", ordering="estado", label={"pendiente": "warning", "aprobada": "success", "rechazada": "danger"})
    def estado_badge(self, obj):
        return obj.estado, obj.get_estado_display()

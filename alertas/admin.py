from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import AutocompleteSelectFilter
from unfold.decorators import display

from .models import Alerta


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

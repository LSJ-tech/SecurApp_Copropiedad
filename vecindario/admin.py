from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.decorators import display

from .models import AlertaCiudadana, PerfilGeografico


@admin.register(PerfilGeografico)
class PerfilGeograficoAdmin(ModelAdmin):
    list_display = ["user", "comuna", "region", "telefono", "fecha_registro"]
    list_filter = ["comuna", "region"]
    list_filter_submit = True
    list_select_related = ["user"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "comuna"]


@admin.register(AlertaCiudadana)
class AlertaCiudadanaAdmin(ModelAdmin):
    list_display = ["tipo_badge", "estado_badge", "autor", "fecha_creacion"]
    list_filter = ["tipo", "estado"]
    list_filter_submit = True
    list_select_related = ["autor__user"]

    @display(description="Tipo", ordering="tipo", label={"robo": "danger", "incendio": "danger", "accidente": "warning", "emergencia_medica": "danger", "persona_extrana": "warning", "fuga_gas": "danger", "fuga_agua": "warning", "atrapado_ascensor": "warning", "objeto_sospechoso": "warning", "rina_disturbio": "danger", "otro": "info", "prueba": "info"})
    def tipo_badge(self, obj):
        return obj.tipo, obj.get_tipo_display()

    @display(description="Estado", ordering="estado", label={"activa": "danger", "resuelta": "success", "falsa_alarma": "warning", "auto_cerrada": "info"})
    def estado_badge(self, obj):
        return obj.estado, obj.get_estado_display()

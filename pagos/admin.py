from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import AutocompleteSelectFilter
from unfold.decorators import display

from .models import Pago


@admin.register(Pago)
class PagoAdmin(ModelAdmin):
    list_display = ["condominio", "donante", "torre", "unidad", "tipo", "plan", "monto", "estado_badge", "fecha_creacion"]
    list_filter = [("condominio", AutocompleteSelectFilter), "tipo", "plan", "estado"]
    list_filter_submit = True
    list_select_related = ["condominio", "membresia__user", "membresia__unidad", "membresia__unidad__torre"]

    @admin.display(description="Donante")
    def donante(self, obj):
        if not obj.membresia:
            return "-"
        return obj.membresia.user.get_full_name() or obj.membresia.user.username

    @admin.display(description="Torre")
    def torre(self, obj):
        if obj.membresia and obj.membresia.unidad and obj.membresia.unidad.torre:
            return obj.membresia.unidad.torre.nombre
        return "-"

    @admin.display(description="Unidad")
    def unidad(self, obj):
        if obj.membresia and obj.membresia.unidad:
            return obj.membresia.unidad.numero
        return "-"

    @display(description="Estado", ordering="estado", label={"pendiente": "warning", "aprobado": "success", "rechazado": "danger"})
    def estado_badge(self, obj):
        return obj.estado, obj.get_estado_display()

from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import AutocompleteSelectFilter

from .models import RegistroIngreso


@admin.register(RegistroIngreso)
class RegistroIngresoAdmin(ModelAdmin):
    list_display = ["nombre_visitante", "unidad", "motivo", "fecha_ingreso", "fecha_salida"]
    list_filter = ["motivo", ("unidad__condominio", AutocompleteSelectFilter)]
    list_filter_submit = True

from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import AutocompleteSelectFilter

from .models import RegistroIngreso


@admin.register(RegistroIngreso)
class RegistroIngresoAdmin(ModelAdmin):
    list_display = ["nombre_visitante", "unidad", "motivo", "fecha_ingreso", "fecha_salida"]
    list_filter = ["motivo", ("unidad__condominio", AutocompleteSelectFilter)]
    list_filter_submit = True
    search_fields = ["nombre_visitante", "motivo", "unidad__numero"]
    # Unidad.__str__ toca unidad.torre o unidad.condominio según el caso --
    # sin ambos acá, cada fila dispara una query extra.
    list_select_related = ["unidad__torre", "unidad__condominio"]

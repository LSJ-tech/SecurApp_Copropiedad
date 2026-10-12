from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import AutocompleteSelectFilter

from .models import Aviso


@admin.register(Aviso)
class AvisoAdmin(ModelAdmin):
    list_display = ["titulo", "condominio", "autor", "fecha_creacion"]
    list_filter = [("condominio", AutocompleteSelectFilter)]
    list_filter_submit = True
    # autor es un Membresia, y Membresia.__str__ toca autor.user y
    # autor.condominio -- sin esos dos, cada fila dispara 2 queries extra.
    list_select_related = ["condominio", "autor__user", "autor__condominio"]

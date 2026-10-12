from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import AutocompleteSelectFilter

from .models import Aviso


@admin.register(Aviso)
class AvisoAdmin(ModelAdmin):
    list_display = ["titulo", "condominio", "autor", "fecha_creacion"]
    list_filter = [("condominio", AutocompleteSelectFilter)]
    list_filter_submit = True

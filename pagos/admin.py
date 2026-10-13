from django.contrib import admin, messages
from django.utils import timezone
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import AutocompleteSelectFilter
from unfold.decorators import display

from .mercadopago_client import cancelar_suscripcion_recurrente
from .models import Pago, SuscripcionRecurrente


@admin.action(description="Cancelar en Mercado Pago (deja de cobrar)")
def cancelar_en_mercadopago(modeladmin, request, queryset):
    for suscripcion in queryset.exclude(estado="cancelada"):
        if cancelar_suscripcion_recurrente(suscripcion):
            suscripcion.estado = "cancelada"
            suscripcion.fecha_cancelacion = timezone.now()
            suscripcion.save(update_fields=["estado", "fecha_cancelacion"])
        else:
            messages.error(request, f"No se pudo cancelar la suscripción recurrente #{suscripcion.pk} en Mercado Pago.")


@admin.action(description="Sincronizar estado con Mercado Pago")
def sincronizar_con_mercadopago(modeladmin, request, queryset):
    """Respaldo manual para cuando el webhook no llega (ver
    sincronizar_estado_suscripcion en pagos/views.py) -- re-consulta cada
    suscripción directo a la API de Mercado Pago, en vez de esperar a que
    avisen solos."""
    from .views import sincronizar_estado_suscripcion

    sincronizadas = 0
    for suscripcion in queryset:
        if sincronizar_estado_suscripcion(suscripcion):
            sincronizadas += 1
        else:
            messages.error(request, f"No se pudo consultar la suscripción recurrente #{suscripcion.pk} en Mercado Pago.")
    if sincronizadas:
        messages.success(request, f"Se consultó el estado de {sincronizadas} suscripción(es) en Mercado Pago.")


@admin.register(SuscripcionRecurrente)
class SuscripcionRecurrenteAdmin(ModelAdmin):
    list_display = ["condominio", "donante", "tipo", "monto", "estado_badge", "fecha_creacion"]
    list_filter = [("condominio", AutocompleteSelectFilter), "tipo", "estado"]
    list_filter_submit = True
    list_select_related = ["condominio", "membresia__user"]
    actions = [sincronizar_con_mercadopago, cancelar_en_mercadopago]
    readonly_fields = ["mercadopago_preapproval_id", "fecha_creacion", "fecha_cancelacion"]

    @admin.display(description="Donante")
    def donante(self, obj):
        if not obj.membresia:
            return "-"
        return obj.membresia.user.get_full_name() or obj.membresia.user.username

    @display(description="Estado", ordering="estado", label={"pendiente": "warning", "autorizada": "success", "pausada": "info", "cancelada": "danger"})
    def estado_badge(self, obj):
        return obj.estado, obj.get_estado_display()


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

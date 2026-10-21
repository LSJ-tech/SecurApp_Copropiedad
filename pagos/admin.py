from django.contrib import admin, messages
from django.utils import timezone
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import AutocompleteSelectFilter
from unfold.decorators import display

from .mercadopago_client import cancelar_suscripcion_recurrente, obtener_preapproval_mercadopago
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


@admin.action(description="Enviar recordatorio de donación pendiente")
def enviar_recordatorio_donacion(modeladmin, request, queryset):
    """Manual, independiente de la ventana automática de 24-48h que ya
    maneja sincronizar_estado_suscripcion -- para cuando devquad quiere
    mandar el empujón a mano (ej. antes o después de esa ventana), sin
    esperar al cron. Solo aplica a donaciones pendientes -- el resto de
    la selección se ignora, sin error."""
    from .views import enviar_correo_recordatorio_donacion

    aplican = queryset.filter(tipo="donacion", estado="pendiente")
    enviados = 0
    for suscripcion in aplican:
        detalle = obtener_preapproval_mercadopago(suscripcion.mercadopago_preapproval_id)
        if not detalle:
            messages.error(request, f"No se pudo consultar la suscripción recurrente #{suscripcion.pk} en Mercado Pago.")
            continue
        suscripcion.recordatorio_enviado_en = timezone.now()
        suscripcion.save(update_fields=["recordatorio_enviado_en"])
        enviar_correo_recordatorio_donacion(suscripcion, detalle.get("init_point", ""))
        enviados += 1
    if enviados:
        messages.success(request, f"Se mandó el recordatorio a {enviados} donación(es) pendiente(s).")
    ignoradas = queryset.exclude(pk__in=aplican.values_list("pk", flat=True)).count()
    if ignoradas:
        messages.warning(request, f"{ignoradas} selección(es) se ignoraron -- el recordatorio solo aplica a donaciones pendientes.")


@admin.register(SuscripcionRecurrente)
class SuscripcionRecurrenteAdmin(ModelAdmin):
    list_display = ["condominio", "donante", "tipo", "monto", "estado_badge", "fecha_creacion"]
    list_filter = [("condominio", AutocompleteSelectFilter), "tipo", "estado"]
    list_filter_submit = True
    list_select_related = ["condominio", "membresia__user"]
    actions = [sincronizar_con_mercadopago, cancelar_en_mercadopago, enviar_recordatorio_donacion]
    readonly_fields = ["mercadopago_preapproval_id", "fecha_creacion", "fecha_cancelacion", "recordatorio_enviado_en"]

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

import datetime
import json
import logging
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import EmailMultiAlternatives
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from core.mixins import MENSAJE_SIN_CONDOMINIO, CondominioRequiredMixin
from core.views import EMAIL_CONTACTO_DEVQUAD

from .mercadopago_client import (
    cancelar_suscripcion_recurrente,
    crear_suscripcion_recurrente,
    obtener_pago_mercadopago,
    obtener_preapproval_mercadopago,
)
from .models import Pago, SuscripcionRecurrente

logger = logging.getLogger(__name__)

MONTO_DONACION = Decimal("2000")

# Mercado Pago manda el tipo de notificación como "type" (cuerpo) o "topic"
# (query string, estilo IPN viejo). "subscription_authorized_payment" quedó
# CONFIRMADO en la práctica (apareció tal cual en un POST real a
# /pago/webhook/, probado con el botón "Simular notificación" del panel de
# Mercado Pago). "payment" ya estaba confirmado de antes (Checkout Pro).
# "preapproval"/"subscription_preapproval" siguen sin confirmar -- no se
# pudo generar una notificación real de cambio de estado para probarlos (ver
# sincronizar_estado_suscripcion más abajo, el respaldo mientras tanto).
TIPOS_NOTIFICACION_PREAPPROVAL = {"preapproval", "subscription_preapproval"}
TIPOS_NOTIFICACION_COBRO = {"payment", "subscription_authorized_payment"}

ESTADO_PREAPPROVAL_A_ESTADO_SUSCRIPCION = {
    "authorized": "autorizada",
    "paused": "pausada",
    "cancelled": "cancelada",
    "pending": "pendiente",
}


def _email_del_pagador(request):
    """payer_email es obligatorio para crear una autorización recurrente en
    Mercado Pago -- el email es opcional al crear una cuenta, así que puede
    venir vacío."""
    return (request.user.email or "").strip()


def _extender_suscripcion(condominio, plan):
    """Una donación aprobada NUNCA debe pasar por acá -- no regala días de
    servicio ni cambia el plan, eso es exclusivo de un cobro de tipo
    'suscripcion' (ver tests de WebhookMercadoPagoTests)."""
    hoy = timezone.localdate()
    desde = condominio.pagado_hasta if condominio.pagado_hasta and condominio.pagado_hasta > hoy else hoy
    condominio.pagado_hasta = desde + datetime.timedelta(days=30)
    condominio.plan = plan
    condominio.save(update_fields=["pagado_hasta", "plan"])


def _crear_pago_por_cobro(suscripcion, payment_id=""):
    """Registra un cobro aprobado de esta suscripción como Pago. Se usa
    tanto desde el webhook (payment_id real) como desde la sincronización
    manual (sin payment_id -- ver sincronizar_estado_suscripcion)."""
    pago = Pago.objects.create(
        condominio=suscripcion.condominio, membresia=suscripcion.membresia,
        suscripcion_recurrente=suscripcion, tipo=suscripcion.tipo,
        plan="premium" if suscripcion.tipo == "suscripcion" else "",
        monto=suscripcion.monto, estado="aprobado",
        mercadopago_payment_id=str(payment_id), fecha_confirmacion=timezone.now(),
    )
    if pago.tipo == "suscripcion":
        _extender_suscripcion(pago.condominio, pago.plan)
    return pago


def enviar_correo_gracias_donacion(suscripcion):
    """Se manda una sola vez, justo en la transición a "autorizada" (ver
    sincronizar_estado_suscripcion) -- nunca bloquea esa sincronización si
    Resend falla, el correo es un plus, no un requisito."""
    membresia = suscripcion.membresia
    if membresia is None or not membresia.user.email:
        return
    user = membresia.user
    mis_donaciones_url = "https://securapp.devquad.cl/mis-donaciones/"
    contexto = {
        "platform_name": settings.PLATFORM_NAME,
        "nombre": user.first_name or user.username,
        "monto": suscripcion.monto,
        "mis_donaciones_url": mis_donaciones_url,
        "email_contacto": EMAIL_CONTACTO_DEVQUAD,
    }
    texto_plano = (
        f"¡Gracias, {contexto['nombre']}!\n\n"
        f"Tu donación de ${suscripcion.monto:.0f}/mes ya quedó activa -- es un aporte directo para seguir "
        f"mejorando {settings.PLATFORM_NAME} para tu comunidad y para muchas otras.\n\n"
        f"Puedes revisarla o cancelarla cuando quieras desde «Mis donaciones»: {mis_donaciones_url}\n\n"
        f"Cualquier duda, escríbenos a {EMAIL_CONTACTO_DEVQUAD}."
    )
    try:
        correo = EmailMultiAlternatives(
            subject=f"¡Gracias por tu donación, {contexto['nombre']}!",
            body=texto_plano,
            from_email=None,
            to=[user.email],
        )
        correo.attach_alternative(render_to_string("core/emails/donacion_gracias.html", contexto), "text/html")
        correo.send()
    except Exception:
        logger.exception("No se pudo enviar el correo de agradecimiento de la donación #%s a %s.", suscripcion.pk, user.email)


def enviar_correo_recordatorio_donacion(suscripcion, autorizar_url):
    """Se manda una sola vez (ver recordatorio_enviado_en), cuando una
    donación lleva más de 24h en "pendiente" sin que nadie la autorice --
    nunca bloquea la sincronización si Resend falla."""
    membresia = suscripcion.membresia
    if membresia is None or not membresia.user.email:
        return
    user = membresia.user
    contexto = {
        "platform_name": settings.PLATFORM_NAME,
        "nombre": user.first_name or user.username,
        "monto": suscripcion.monto,
        "autorizar_url": autorizar_url,
        "email_contacto": EMAIL_CONTACTO_DEVQUAD,
    }
    texto_plano = (
        f"Hola {contexto['nombre']},\n\n"
        f"Notamos que empezaste a activar una donación de ${suscripcion.monto:.0f}/mes a {settings.PLATFORM_NAME}, "
        f"pero te quedó faltando el último paso: autorizarla en Mercado Pago.\n\n"
        f"Si todavía quieres hacerla, termina de autorizarla acá: {autorizar_url}\n\n"
        f"Si no quieres seguir, no tienes que hacer nada -- no se te cobrará nada, y esta solicitud se cancela "
        f"sola en un par de días.\n\n"
        f"Cualquier duda, escríbenos a {EMAIL_CONTACTO_DEVQUAD}."
    )
    try:
        correo = EmailMultiAlternatives(
            subject="Te falta un paso para tu donación",
            body=texto_plano,
            from_email=None,
            to=[user.email],
        )
        correo.attach_alternative(render_to_string("core/emails/donacion_recordatorio.html", contexto), "text/html")
        correo.send()
    except Exception:
        logger.exception("No se pudo enviar el recordatorio de donación pendiente #%s a %s.", suscripcion.pk, user.email)


def _aplicar_nuevo_estado_desde_mercadopago(suscripcion, detalle):
    """Si Mercado Pago reporta un estado distinto al que tenemos guardado,
    lo aplica y dispara el correo de agradecimiento si es una donación que
    recién se autorizó."""
    nuevo_estado = ESTADO_PREAPPROVAL_A_ESTADO_SUSCRIPCION.get(detalle.get("status"))
    if not nuevo_estado or nuevo_estado == suscripcion.estado:
        return

    es_donacion_recien_autorizada = nuevo_estado == "autorizada" and suscripcion.tipo == "donacion"
    suscripcion.estado = nuevo_estado
    if nuevo_estado == "cancelada" and not suscripcion.fecha_cancelacion:
        suscripcion.fecha_cancelacion = timezone.now()
        suscripcion.save(update_fields=["estado", "fecha_cancelacion"])
    else:
        suscripcion.save(update_fields=["estado"])
    if es_donacion_recien_autorizada:
        enviar_correo_gracias_donacion(suscripcion)


def _enviar_recordatorio_donacion_si_corresponde(suscripcion, detalle):
    """Recordatorio a mitad de camino del plazo de 48h (ver
    _cancelar_donacion_abandonada_si_corresponde) -- solo donaciones, solo
    una vez (recordatorio_enviado_en), y solo dentro de la ventana 24h-48h
    (pasadas las 48h ya se cancela sola, no tiene sentido pedirle que
    termine de autorizar algo que se está por cancelar en la misma
    pasada)."""
    antiguedad = timezone.now() - suscripcion.fecha_creacion
    if not (
        suscripcion.tipo == "donacion"
        and suscripcion.estado == "pendiente"
        and suscripcion.recordatorio_enviado_en is None
        and datetime.timedelta(hours=24) <= antiguedad < datetime.timedelta(hours=48)
    ):
        return
    suscripcion.recordatorio_enviado_en = timezone.now()
    suscripcion.save(update_fields=["recordatorio_enviado_en"])
    enviar_correo_recordatorio_donacion(suscripcion, detalle.get("init_point", ""))


def _cancelar_donacion_abandonada_si_corresponde(suscripcion):
    """Una donación "pendiente" que nadie autorizó NI canceló se queda así
    en Mercado Pago indefinidamente (no vence sola del otro lado) -- se da
    por abandonada pasadas 48h desde que se creó y se cancela de verdad en
    Mercado Pago (no solo local, para no dejar un preapproval zombie que
    alguien autorice por sorpresa meses después). Solo para donaciones:
    una suscripción SaaS de condominio pendiente es una relación comercial
    real, no se cancela sola sin que nadie la revise."""
    if not (
        suscripcion.tipo == "donacion"
        and suscripcion.estado == "pendiente"
        and timezone.now() - suscripcion.fecha_creacion > datetime.timedelta(hours=48)
        and cancelar_suscripcion_recurrente(suscripcion)
    ):
        return
    suscripcion.estado = "cancelada"
    suscripcion.fecha_cancelacion = timezone.now()
    suscripcion.save(update_fields=["estado", "fecha_cancelacion"])


def _completar_pago_faltante_si_corresponde(suscripcion):
    """Mercado Pago solo pasa una autorización a "authorized" después de
    cobrar la primera cuota con éxito (lo confirmamos nosotros mismos: la
    pantalla "Pagaste $X" aparece apenas se autoriza). Si el webhook nunca
    avisó ese primer cobro, el Pago correspondiente nunca se creó -- se
    genera acá para no dejar un cobro real sin registrar. No se limita al
    momento exacto de la transición: una suscripción puede haber quedado
    "Autorizada" en una sincronización anterior (antes de este fix) sin su
    Pago, así que se revisa cada vez que el estado es "autorizada", y solo
    se crea si de verdad no hay ningún Pago todavía (no duplica)."""
    if suscripcion.estado == "autorizada" and not suscripcion.cobros.exists():
        _crear_pago_por_cobro(suscripcion)


def sincronizar_estado_suscripcion(suscripcion):
    """Re-consulta el estado real de esta SuscripcionRecurrente en Mercado
    Pago y lo actualiza -- mismo código que usa el webhook al recibir un
    cambio de preapproval, pero disparado a pedido (ver la acción
    "Sincronizar con Mercado Pago" en el admin) para los casos donde el
    webhook no llega. Devuelve True si se pudo consultar a Mercado Pago
    (sin importar si el estado cambió), False si no respondió."""
    detalle = obtener_preapproval_mercadopago(suscripcion.mercadopago_preapproval_id)
    if not detalle:
        return False

    _aplicar_nuevo_estado_desde_mercadopago(suscripcion, detalle)
    _enviar_recordatorio_donacion_si_corresponde(suscripcion, detalle)
    _cancelar_donacion_abandonada_si_corresponde(suscripcion)
    _completar_pago_faltante_si_corresponde(suscripcion)

    return True


class DonarView(LoginRequiredMixin, View):
    """Cualquier miembro (residente o delegado) puede activar una donación
    mensual automática para apoyar el desarrollo de la plataforma -- cobro
    recurrente vía Mercado Pago (API Preapproval) hasta que la cancele.
    Monto fijo (MONTO_DONACION), no lo elige quien dona."""

    def post(self, request, *args, **kwargs):
        membresia = getattr(request.user, "membresia", None)
        if membresia is None:
            messages.error(request, MENSAJE_SIN_CONDOMINIO)
            return redirect("login")

        if not settings.MERCADOPAGO_ACCESS_TOKEN:
            messages.error(request, "El pago en línea todavía no está disponible. Escríbenos para donar.")
            return redirect("inicio")

        email = _email_del_pagador(request)
        if not email:
            messages.error(request, "Agrega tu email en «Mi perfil» antes de activar una donación automática.")
            return redirect("inicio")

        if SuscripcionRecurrente.objects.filter(membresia=membresia, tipo="donacion", estado__in=["pendiente", "autorizada"]).exists():
            messages.error(request, "Ya tienes una donación automática activa.")
            return redirect("inicio")

        suscripcion = SuscripcionRecurrente.objects.create(condominio=membresia.condominio, membresia=membresia, tipo="donacion", monto=MONTO_DONACION)
        url_autorizacion = crear_suscripcion_recurrente(suscripcion, email, request)
        if not url_autorizacion:
            suscripcion.delete()
            messages.error(request, "No pudimos iniciar la donación automática. Intenta de nuevo en un momento.")
            return redirect("inicio")
        return redirect(url_autorizacion)


class CancelarDonacionRecurrenteView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        membresia = getattr(request.user, "membresia", None)
        if membresia is None:
            messages.error(request, MENSAJE_SIN_CONDOMINIO)
            return redirect("login")

        suscripcion = SuscripcionRecurrente.objects.filter(
            membresia=membresia, tipo="donacion", estado__in=["pendiente", "autorizada"],
        ).first()
        if not suscripcion:
            messages.error(request, "No tienes ninguna donación automática activa.")
            return redirect("inicio")

        if cancelar_suscripcion_recurrente(suscripcion):
            suscripcion.estado = "cancelada"
            suscripcion.fecha_cancelacion = timezone.now()
            suscripcion.save(update_fields=["estado", "fecha_cancelacion"])
            messages.success(request, "Listo, cancelamos tu donación automática. No se harán más cobros.")
        else:
            messages.error(request, "No pudimos cancelar la donación en Mercado Pago. Intenta de nuevo o escríbenos.")
        return redirect("inicio")


class PagoResultadoView(LoginRequiredMixin, TemplateView):
    """A donde vuelve el navegador tras autorizar el cobro (o cancelar). Solo
    informativa -- la confirmación real llega por separado a WebhookMercadoPagoView."""

    template_name = "pagos/pago_resultado.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["estado"] = self.request.GET.get("status", "")
        return context


class MisDonacionesView(CondominioRequiredMixin, TemplateView):
    """Las donaciones son voluntarias y personales -- cada miembro ve
    únicamente su propio historial, nadie más."""

    template_name = "pagos/mis_donaciones.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["donacion_actual"] = SuscripcionRecurrente.objects.filter(
            membresia=self.membresia, tipo="donacion",
        ).order_by("-fecha_creacion").first()
        pagos_donacion = Pago.objects.filter(membresia=self.membresia, tipo="donacion").order_by("-fecha_creacion")
        context["pagos_donacion"] = pagos_donacion
        aprobados = [p for p in pagos_donacion if p.estado == "aprobado"]
        context["total_donado"] = sum((p.monto for p in aprobados), Decimal("0"))
        context["cantidad_aportes"] = len(aprobados)
        return context


@method_decorator(csrf_exempt, name="dispatch")
class WebhookMercadoPagoView(View):
    """Mercado Pago llama acá server-a-server. Nunca se confía en el cuerpo
    del POST: siempre se re-consulta el recurso por ID antes de aprobar nada.

    Maneja dos tipos de notificación: cambios de estado de la autorización
    recurrente (TIPOS_NOTIFICACION_PREAPPROVAL) y cobros individuales
    dentro de un ciclo recurrente (TIPOS_NOTIFICACION_COBRO) -- ver la nota
    sobre los valores de "type" sin verificar, arriba de este archivo."""

    def post(self, request, *args, **kwargs):
        try:
            datos = json.loads(request.body or "{}")
        except ValueError:
            return HttpResponse(status=400)

        recurso_id = (datos.get("data") or {}).get("id") or request.GET.get("id") or request.GET.get("data.id")
        if not recurso_id:
            return HttpResponse(status=200)

        tipo_notificacion = datos.get("type") or request.GET.get("type") or request.GET.get("topic") or ""

        if tipo_notificacion in TIPOS_NOTIFICACION_PREAPPROVAL:
            self._manejar_cambio_preapproval(recurso_id)
        else:
            # Por defecto se trata como un cobro -- cubre "payment" (ya
            # confirmado) y cualquier "subscription_authorized_payment" que
            # llegue, además de notificaciones sin "type" (algunos webhooks
            # viejos de Mercado Pago no lo mandan).
            self._manejar_cobro(recurso_id)

        return HttpResponse(status=200)

    def _manejar_cambio_preapproval(self, preapproval_id):
        suscripcion = SuscripcionRecurrente.objects.filter(mercadopago_preapproval_id=str(preapproval_id)).first()
        if not suscripcion:
            return
        sincronizar_estado_suscripcion(suscripcion)

    def _manejar_cobro(self, payment_id):
        if Pago.objects.filter(mercadopago_payment_id=str(payment_id)).exists():
            return  # Mercado Pago puede reintentar el mismo webhook -- no duplicar el cobro.

        detalle = obtener_pago_mercadopago(payment_id)
        if not detalle or detalle.get("status") != "approved":
            return

        # El campo que liga un pago a su autorización recurrente no está
        # confirmado contra la documentación real -- se prueban los
        # nombres más probables. Si ninguno aparece, se registra el error
        # en vez de perder el cobro silenciosamente (ver mensaje al usuario
        # sobre verificar esto con el sandbox).
        preapproval_id = (
            detalle.get("preapproval_id")
            or (detalle.get("metadata") or {}).get("preapproval_id")
            or detalle.get("external_reference")
        )
        suscripcion = SuscripcionRecurrente.objects.filter(mercadopago_preapproval_id=str(preapproval_id)).first() if preapproval_id else None
        if not suscripcion:
            logger.error(
                "Webhook de Mercado Pago: cobro #%s aprobado pero no se pudo relacionar con ninguna "
                "SuscripcionRecurrente (preapproval_id probado: %r). Revisar a mano.",
                payment_id, preapproval_id,
            )
            return

        _crear_pago_por_cobro(suscripcion, payment_id)

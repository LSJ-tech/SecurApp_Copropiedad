import datetime
import json
import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from .mercadopago_client import (
    cancelar_suscripcion_recurrente,
    crear_suscripcion_recurrente,
    obtener_pago_mercadopago,
    obtener_preapproval_mercadopago,
)
from .models import Pago, SuscripcionRecurrente

logger = logging.getLogger(__name__)

MONTO_SUSCRIPCION = Decimal("19990")

# Mercado Pago manda el tipo de notificación como "type" (cuerpo) o "topic"
# (query string, estilo IPN viejo). Estos valores de "subscription_*" están
# SIN VERIFICAR contra la documentación real (bloqueada desde este entorno
# al momento de escribir esto) -- confirmar contra el sandbox real de
# Mercado Pago antes de confiar en este camino en producción. "payment" sí
# está confirmado (ya se usaba para Checkout Pro).
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
    Mercado Pago -- el autorregistro de directiva no pide email (ver
    RegistroCondominioForm), así que puede venir vacío."""
    return (request.user.email or "").strip()


class DonarView(LoginRequiredMixin, View):
    """Cualquier miembro (directiva, administración, conserjería o residente)
    puede activar una donación mensual automática para apoyar el desarrollo
    de la plataforma -- cobro recurrente vía Mercado Pago (API Preapproval)
    hasta que la cancele, sin relación con la suscripción del condominio."""

    def post(self, request, *args, **kwargs):
        membresia = getattr(request.user, "membresia", None)
        if membresia is None:
            messages.error(request, "Tu cuenta no está vinculada a ningún condominio.")
            return redirect("login")

        if not settings.MERCADOPAGO_ACCESS_TOKEN:
            messages.error(request, "El pago en línea todavía no está disponible. Escríbenos para donar.")
            return redirect("inicio")

        email = _email_del_pagador(request)
        if not email:
            messages.error(request, "Agrega tu email en «Mi perfil» antes de activar una donación automática.")
            return redirect("inicio")

        if SuscripcionRecurrente.objects.filter(membresia=membresia, tipo="donacion", estado__in=["pendiente", "autorizada"]).exists():
            messages.error(request, "Ya tienes una donación automática activa. Cancélala primero si quieres cambiar el monto.")
            return redirect("inicio")

        try:
            monto = Decimal((request.POST.get("monto") or "").replace(",", "."))
        except InvalidOperation:
            monto = None
        if not monto or monto <= 0:
            messages.error(request, "Ingresa un monto válido para donar.")
            return redirect("inicio")

        suscripcion = SuscripcionRecurrente.objects.create(condominio=membresia.condominio, membresia=membresia, tipo="donacion", monto=monto)
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
            messages.error(request, "Tu cuenta no está vinculada a ningún condominio.")
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


class SuscripcionPagarView(LoginRequiredMixin, View):
    """Solo directiva o administración pueden activar el cobro automático
    mensual de la suscripción del condominio -- monto fijo. Cobro recurrente
    vía Mercado Pago (API Preapproval) hasta que se cancele: cada cobro
    aprobado extiende Condominio.pagado_hasta 30 días (ver WebhookMercadoPagoView)."""

    def post(self, request, *args, **kwargs):
        membresia = getattr(request.user, "membresia", None)
        if membresia is None:
            messages.error(request, "Tu cuenta no está vinculada a ningún condominio.")
            return redirect("login")
        if membresia.rol not in ("administracion", "directiva"):
            messages.error(request, "Activar el pago de la suscripción es exclusivo de directiva/administración.")
            return redirect("inicio")

        if not settings.MERCADOPAGO_ACCESS_TOKEN:
            messages.error(request, "El pago en línea todavía no está disponible. Escríbenos para coordinar el pago.")
            return redirect("inicio")

        email = _email_del_pagador(request)
        if not email:
            messages.error(request, "Agrega tu email en «Mi perfil» antes de activar el cobro automático.")
            return redirect("inicio")

        condominio = membresia.condominio
        if SuscripcionRecurrente.objects.filter(condominio=condominio, tipo="suscripcion", estado__in=["pendiente", "autorizada"]).exists():
            messages.error(request, "Ya existe una suscripción automática activa para este condominio.")
            return redirect("inicio")

        suscripcion = SuscripcionRecurrente.objects.create(
            condominio=condominio, membresia=membresia, tipo="suscripcion", monto=MONTO_SUSCRIPCION,
        )
        url_autorizacion = crear_suscripcion_recurrente(suscripcion, email, request)
        if not url_autorizacion:
            suscripcion.delete()
            messages.error(request, "No pudimos iniciar el pago. Intenta de nuevo en un momento.")
            return redirect("inicio")
        return redirect(url_autorizacion)


class CancelarSuscripcionRecurrenteView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        membresia = getattr(request.user, "membresia", None)
        if membresia is None:
            messages.error(request, "Tu cuenta no está vinculada a ningún condominio.")
            return redirect("login")
        if membresia.rol not in ("administracion", "directiva"):
            messages.error(request, "Cancelar la suscripción es exclusivo de directiva/administración.")
            return redirect("inicio")

        suscripcion = SuscripcionRecurrente.objects.filter(
            condominio=membresia.condominio, tipo="suscripcion", estado__in=["pendiente", "autorizada"],
        ).first()
        if not suscripcion:
            messages.error(request, "No hay ninguna suscripción automática activa para cancelar.")
            return redirect("inicio")

        if cancelar_suscripcion_recurrente(suscripcion):
            suscripcion.estado = "cancelada"
            suscripcion.fecha_cancelacion = timezone.now()
            suscripcion.save(update_fields=["estado", "fecha_cancelacion"])
            messages.success(request, "Listo, cancelamos el cobro automático. No se harán más cobros -- el acceso sigue activo hasta la fecha ya pagada.")
        else:
            messages.error(request, "No pudimos cancelar la suscripción en Mercado Pago. Intenta de nuevo o escríbenos.")
        return redirect("inicio")


class PagoResultadoView(LoginRequiredMixin, TemplateView):
    """A donde vuelve el navegador tras autorizar el cobro (o cancelar). Solo
    informativa -- la confirmación real llega por separado a WebhookMercadoPagoView."""

    template_name = "pagos/pago_resultado.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["estado"] = self.request.GET.get("status", "")
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
        detalle = obtener_preapproval_mercadopago(preapproval_id)
        if not detalle:
            return
        suscripcion = SuscripcionRecurrente.objects.filter(mercadopago_preapproval_id=str(preapproval_id)).first()
        if not suscripcion:
            return
        nuevo_estado = ESTADO_PREAPPROVAL_A_ESTADO_SUSCRIPCION.get(detalle.get("status"))
        if not nuevo_estado or nuevo_estado == suscripcion.estado:
            return
        suscripcion.estado = nuevo_estado
        if nuevo_estado == "cancelada" and not suscripcion.fecha_cancelacion:
            suscripcion.fecha_cancelacion = timezone.now()
            suscripcion.save(update_fields=["estado", "fecha_cancelacion"])
        else:
            suscripcion.save(update_fields=["estado"])

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

        pago = Pago.objects.create(
            condominio=suscripcion.condominio, membresia=suscripcion.membresia,
            suscripcion_recurrente=suscripcion, tipo=suscripcion.tipo,
            plan="premium" if suscripcion.tipo == "suscripcion" else "",
            monto=suscripcion.monto, estado="aprobado",
            mercadopago_payment_id=str(payment_id), fecha_confirmacion=timezone.now(),
        )
        if pago.tipo == "suscripcion":
            self._extender_suscripcion(pago)

    def _extender_suscripcion(self, pago):
        """Una donación aprobada NUNCA debe pasar por acá -- no regala días
        de servicio ni cambia el plan, eso es exclusivo de un pago de tipo
        'suscripcion' (ver tests de WebhookMercadoPagoTests)."""
        condominio = pago.condominio
        hoy = timezone.localdate()
        desde = condominio.pagado_hasta if condominio.pagado_hasta and condominio.pagado_hasta > hoy else hoy
        condominio.pagado_hasta = desde + datetime.timedelta(days=30)
        condominio.plan = pago.plan
        condominio.save(update_fields=["pagado_hasta", "plan"])

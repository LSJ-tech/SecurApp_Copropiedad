import logging

import mercadopago
from django.conf import settings

logger = logging.getLogger(__name__)


def _access_token():
    return settings.MERCADOPAGO_ACCESS_TOKEN.strip()


def _sdk():
    return mercadopago.SDK(_access_token())


def _es_credencial_de_prueba():
    return _access_token().startswith("TEST-")


def crear_suscripcion_recurrente(suscripcion, payer_email, request):
    """Crea la autorización de cobro automático mensual (API Preapproval,
    no Checkout Pro) para esta SuscripcionRecurrente y devuelve la URL a la
    que hay que redirigir para que la persona autorice el cobro con su
    tarjeta. Sin end_date -- queda cobrando indefinidamente hasta que se
    cancele (ver cancelar_suscripcion_recurrente). None si Mercado Pago
    rechazó la solicitud."""
    base_url = request.build_absolute_uri("/").rstrip("/")
    if suscripcion.tipo == "donacion":
        origen = suscripcion.condominio.nombre
        if suscripcion.membresia and suscripcion.membresia.unidad:
            unidad = suscripcion.membresia.unidad
            if unidad.torre:
                origen = f"{suscripcion.condominio.nombre}, Torre {unidad.torre.nombre} - Depto {unidad.numero}"
            else:
                origen = f"{suscripcion.condominio.nombre}, Depto {unidad.numero}"
        razon = f"Donación mensual a {settings.PLATFORM_NAME} - {origen}"
    else:
        razon = f"Suscripción mensual {settings.PLATFORM_NAME} - {suscripcion.condominio.nombre}"

    preapproval_object = {
        "reason": razon,
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": float(suscripcion.monto),
            "currency_id": "CLP",
        },
        "payer_email": payer_email,
        "back_url": f"{base_url}/pago/resultado/",
        "external_reference": str(suscripcion.pk),
        "notification_url": f"{base_url}/pago/webhook/",
    }
    resultado = _sdk().preapproval().create(preapproval_object)
    if not resultado.is_success:
        logger.error(
            "Mercado Pago rechazó la suscripción recurrente #%s: status=%s respuesta=%s",
            suscripcion.pk, resultado.get("status"), resultado.get("response"),
        )
        return None

    datos = resultado["response"]
    suscripcion.mercadopago_preapproval_id = datos["id"]
    suscripcion.save(update_fields=["mercadopago_preapproval_id"])

    # Mismo criterio que Checkout Pro (preferencias): con credencial de
    # prueba, usar el init_point de sandbox si Mercado Pago lo entrega --
    # sin confirmar si Preapproval siempre lo incluye, por eso el fallback.
    if _es_credencial_de_prueba() and datos.get("sandbox_init_point"):
        return datos["sandbox_init_point"]
    return datos.get("init_point")


def cancelar_suscripcion_recurrente(suscripcion):
    """Cancela la autorización de cobro automático en Mercado Pago -- deja
    de cobrar desde el próximo ciclo. True si Mercado Pago confirmó la
    cancelación."""
    resultado = _sdk().preapproval().update(suscripcion.mercadopago_preapproval_id, {"status": "cancelled"})
    if not resultado.is_success:
        logger.error(
            "No se pudo cancelar la suscripción recurrente #%s en Mercado Pago: status=%s respuesta=%s",
            suscripcion.pk, resultado.get("status"), resultado.get("response"),
        )
        return False
    return True


def obtener_preapproval_mercadopago(preapproval_id):
    """Consulta una autorización recurrente por su ID directo a la API de
    Mercado Pago. Nunca se confía en el estado que venga en el cuerpo del
    webhook."""
    resultado = _sdk().preapproval().get(preapproval_id)
    if not resultado.is_success:
        logger.error(
            "No se pudo consultar la suscripción recurrente %s en Mercado Pago: status=%s respuesta=%s",
            repr(preapproval_id), resultado.get("status"), resultado.get("response"),
        )
        return None
    return resultado["response"]


def obtener_pago_mercadopago(payment_id):
    """Consulta un pago (un cobro individual, único o dentro de un ciclo
    recurrente) por su ID directo a la API de Mercado Pago. Nunca se confía
    en el estado que venga en el cuerpo del webhook."""
    resultado = _sdk().payment().get(payment_id)
    if not resultado.is_success:
        logger.error(
            "No se pudo consultar el pago %s en Mercado Pago: status=%s respuesta=%s",
            repr(payment_id), resultado.get("status"), resultado.get("response"),
        )
        return None
    return resultado["response"]

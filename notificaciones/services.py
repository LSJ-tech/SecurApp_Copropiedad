import json
import logging

import requests
from django.conf import settings
from pywebpush import WebPushException, webpush

from .models import DispositivoPush, SuscripcionWebPush

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def enviar_push_a_condominio(condominio, titulo, cuerpo, data=None, excluir_user_id=None, torre=None):
    """Envía una push notification a todos los dispositivos registrados de
    usuarios con membresía en `condominio`, vía el servicio de push de Expo
    (que a su vez enruta a FCM en Android y APNs en iOS -- no hace falta
    hablar directo con Firebase mientras la app sea 100% Expo).

    Si se pasa `torre`, se acota a los residentes de esa torre (ej. un
    aviso de un delegado, publicado solo para su propia torre).

    No lanza excepción si Expo falla o no hay red: una alerta no debe
    fallar en crearse solo porque el push no salió, así que el error
    solo se registra en el log.
    """
    dispositivos = DispositivoPush.objects.filter(user__membresia__condominio=condominio)
    if torre:
        dispositivos = dispositivos.filter(user__membresia__unidad__torre=torre)
    if excluir_user_id:
        dispositivos = dispositivos.exclude(user_id=excluir_user_id)

    tokens = list(dispositivos.values_list("token", flat=True))
    if not tokens:
        return

    mensajes = [
        {"to": token, "title": titulo, "body": cuerpo, "data": data or {}, "sound": "default", "priority": "high"}
        for token in tokens
    ]

    # Expo recomienda lotes de máximo 100 mensajes por request.
    for i in range(0, len(mensajes), 100):
        lote = mensajes[i:i + 100]
        try:
            respuesta = requests.post(EXPO_PUSH_URL, json=lote, timeout=10)
            respuesta.raise_for_status()
        except requests.RequestException:
            logger.exception("Falló el envío de push a Expo para %s dispositivos.", len(lote))


def enviar_web_push_a_condominio(condominio, titulo, cuerpo, data=None, excluir_user_id=None, torre=None):
    """Igual que enviar_push_a_condominio, pero para navegadores (la PWA)
    vía el protocolo estándar de Web Push -- sin pasar por Expo. No hace
    nada si no hay VAPID configurado (todavía no se armó en producción) ni
    si nadie se suscribió."""
    if not settings.VAPID_PRIVATE_KEY:
        return

    suscripciones = SuscripcionWebPush.objects.filter(user__membresia__condominio=condominio)
    if torre:
        suscripciones = suscripciones.filter(user__membresia__unidad__torre=torre)
    if excluir_user_id:
        suscripciones = suscripciones.exclude(user_id=excluir_user_id)

    payload = json.dumps({"title": titulo, "body": cuerpo, "data": data or {}})
    for suscripcion in suscripciones:
        try:
            webpush(
                subscription_info={
                    "endpoint": suscripcion.endpoint,
                    "keys": {"p256dh": suscripcion.p256dh, "auth": suscripcion.auth},
                },
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": f"mailto:{settings.VAPID_CLAIMS_EMAIL}"},
            )
        except WebPushException as error:
            estado = getattr(error.response, "status_code", None)
            if estado in (404, 410):
                # El navegador descartó la suscripción (desinstaló la PWA,
                # borró datos del sitio, etc.) -- ya no sirve, se limpia.
                suscripcion.delete()
            else:
                logger.exception("Falló el envío de web push a la suscripción #%s.", suscripcion.pk)


def enviar_push_a_usuarios(user_ids, titulo, cuerpo, data=None):
    """Igual que enviar_push_a_condominio, pero para una lista suelta de
    user_id en vez de un condominio -- usado por la red vecinal geográfica
    (vecindario), que no tiene condominio de por medio. Se duplica en vez
    de generalizar enviar_push_a_condominio con un queryset arbitrario, a
    propósito, para no arriesgar romper esa función ya probada y en
    producción."""
    dispositivos = DispositivoPush.objects.filter(user_id__in=user_ids)
    tokens = list(dispositivos.values_list("token", flat=True))
    if not tokens:
        return

    mensajes = [
        {"to": token, "title": titulo, "body": cuerpo, "data": data or {}, "sound": "default", "priority": "high"}
        for token in tokens
    ]
    for i in range(0, len(mensajes), 100):
        lote = mensajes[i:i + 100]
        try:
            respuesta = requests.post(EXPO_PUSH_URL, json=lote, timeout=10)
            respuesta.raise_for_status()
        except requests.RequestException:
            logger.exception("Falló el envío de push a Expo para %s dispositivos.", len(lote))


def enviar_web_push_a_usuarios(user_ids, titulo, cuerpo, data=None):
    """Igual que enviar_web_push_a_condominio, pero para una lista suelta
    de user_id (ver enviar_push_a_usuarios)."""
    if not settings.VAPID_PRIVATE_KEY:
        return

    suscripciones = SuscripcionWebPush.objects.filter(user_id__in=user_ids)
    payload = json.dumps({"title": titulo, "body": cuerpo, "data": data or {}})
    for suscripcion in suscripciones:
        try:
            webpush(
                subscription_info={
                    "endpoint": suscripcion.endpoint,
                    "keys": {"p256dh": suscripcion.p256dh, "auth": suscripcion.auth},
                },
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": f"mailto:{settings.VAPID_CLAIMS_EMAIL}"},
            )
        except WebPushException as error:
            estado = getattr(error.response, "status_code", None)
            if estado in (404, 410):
                suscripcion.delete()
            else:
                logger.exception("Falló el envío de web push a la suscripción #%s.", suscripcion.pk)

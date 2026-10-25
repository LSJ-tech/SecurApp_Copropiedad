from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .mercadopago_client import cancelar_suscripcion_recurrente
from .models import Pago, SuscripcionRecurrente
from .serializers import DonacionActualSerializer, PagoResumenSerializer
from .views import DonacionYaActivaError, MercadoPagoRechazoError, _crear_donacion, _email_del_pagador

MENSAJE_SIN_MEMBRESIA_PERSONAL = "Esta cuenta no tiene una membresía personal."


def _membresia_o_409(request):
    """Las donaciones son personales (SuscripcionRecurrente.membresia) --
    nunca del condominio activo de un devquad, que no tiene Membresia
    propia. Devuelve (membresia, None) o (None, Response 409)."""
    membresia = getattr(request.user, "membresia", None)
    if membresia is None:
        return None, Response({"detail": MENSAJE_SIN_MEMBRESIA_PERSONAL}, status=409)
    return membresia, None


class MiDonacionApiView(APIView):
    """Estado de la donación propia + historial -- equivalente a
    MisDonacionesView del panel web."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=None)
    def get(self, request):
        membresia, error = _membresia_o_409(request)
        if error:
            return error

        donacion_actual = (
            SuscripcionRecurrente.objects.filter(membresia=membresia, tipo="donacion")
            .order_by("-fecha_creacion")
            .first()
        )
        pagos_donacion = Pago.objects.filter(membresia=membresia, tipo="donacion").order_by("-fecha_creacion")
        aprobados = [p for p in pagos_donacion if p.estado == "aprobado"]
        total_donado = sum((p.monto for p in aprobados), Decimal("0"))

        return Response({
            "donacion_actual": DonacionActualSerializer(donacion_actual).data if donacion_actual else None,
            "pagos": PagoResumenSerializer(pagos_donacion, many=True).data,
            "total_donado": f"{total_donado:.2f}",
            "cantidad_aportes": len(aprobados),
        })


class DonarApiView(APIView):
    """Activa una donación mensual automática -- equivalente a DonarView
    del panel web, mismas condiciones y mismos mensajes."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=None)
    def post(self, request):
        membresia, error = _membresia_o_409(request)
        if error:
            return error

        if not settings.MERCADOPAGO_ACCESS_TOKEN:
            return Response(
                {"detail": "El pago en línea todavía no está disponible. Escríbenos para donar."}, status=400,
            )

        email = _email_del_pagador(request)
        if not email:
            return Response(
                {"detail": "Agrega tu email en «Mi perfil» antes de activar una donación automática."}, status=400,
            )

        if SuscripcionRecurrente.objects.filter(membresia=membresia, tipo="donacion", estado__in=["pendiente", "autorizada"]).exists():
            return Response({"detail": "Ya tienes una donación automática activa."}, status=409)

        try:
            url_autorizacion = _crear_donacion(membresia, email, request)
        except DonacionYaActivaError:
            return Response({"detail": "Ya tienes una donación automática activa."}, status=409)
        except MercadoPagoRechazoError:
            return Response(
                {"detail": "No pudimos iniciar la donación automática. Intenta de nuevo en un momento."}, status=502,
            )
        return Response({"url_autorizacion": url_autorizacion}, status=201)


class CancelarDonacionApiView(APIView):
    """Cancela la donación activa propia -- equivalente a
    CancelarDonacionRecurrenteView del panel web."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=None)
    def post(self, request):
        membresia, error = _membresia_o_409(request)
        if error:
            return error

        suscripcion = SuscripcionRecurrente.objects.filter(
            membresia=membresia, tipo="donacion", estado__in=["pendiente", "autorizada"],
        ).first()
        if not suscripcion:
            return Response({"detail": "No tienes ninguna donación automática activa."}, status=404)

        if not cancelar_suscripcion_recurrente(suscripcion):
            return Response(
                {"detail": "No pudimos cancelar la donación en Mercado Pago. Intenta de nuevo o escríbenos."}, status=400,
            )

        suscripcion.estado = "cancelada"
        suscripcion.fecha_cancelacion = timezone.now()
        suscripcion.save(update_fields=["estado", "fecha_cancelacion"])
        return Response({"detail": "Listo, cancelamos tu donación automática. No se harán más cobros."})

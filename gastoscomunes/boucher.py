import hashlib
import logging
from io import BytesIO

from django.core.mail import EmailMessage
from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A6
from reportlab.pdfgen import canvas

NAVY = HexColor("#1A2E40")
TERRACOTA = HexColor("#E07A5F")
GRIS = HexColor("#6B7280")
logger = logging.getLogger(__name__)


def _codigo_verificacion(cuota):
    base = f"{cuota.pk}-{cuota.monto}-{cuota.fecha_pago}-{cuota.gasto_comun.periodo}"
    return hashlib.sha256(base.encode()).hexdigest()[:8].upper()


def nombre_archivo_boucher(cuota):
    return f"boucher_{cuota.unidad.numero}_{cuota.gasto_comun.periodo}.pdf".replace(" ", "_")


def generar_boucher_pdf_bytes(cuota):
    """Comprobante de pago de una cuota de gasto común -- reemplaza el talonario
    de papel que llena a mano quien cobra. Firma electrónica simple (un sello
    con código de verificación derivado de los datos del pago), no una firma
    electrónica avanzada/certificada -- no corresponde para un comprobante."""
    condominio = cuota.gasto_comun.condominio
    unidad = cuota.unidad
    ancho, alto = A6
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A6)

    c.setFillColor(NAVY)
    c.rect(0, alto - 60, ancho, 60, fill=True, stroke=False)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(ancho / 2, alto - 35, "SecurApp Copropiedad")
    c.setFont("Helvetica", 9)
    c.drawCentredString(ancho / 2, alto - 50, "Comprobante de pago")

    y = alto - 85
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(ancho / 2, y, condominio.nombre)
    y -= 25

    filas = []
    if unidad.torre:
        filas.append((f"{condominio.etiqueta_torre}", unidad.torre.nombre))
    filas.extend([
        (f"{condominio.etiqueta_unidad} N°", unidad.numero),
        ("Periodo", cuota.gasto_comun.periodo),
        ("Fecha de pago", str(cuota.fecha_pago) if cuota.fecha_pago else "—"),
    ])

    c.setFont("Helvetica", 10)
    for etiqueta, valor in filas:
        c.setFillColor(GRIS)
        c.drawString(20, y, etiqueta)
        c.setFillColor(NAVY)
        c.drawRightString(ancho - 20, y, str(valor))
        y -= 18

    y -= 10
    c.setStrokeColor(GRIS)
    c.line(20, y, ancho - 20, y)
    y -= 25

    c.setFillColor(GRIS)
    c.setFont("Helvetica", 10)
    c.drawString(20, y, "Total pagado")
    c.setFillColor(TERRACOTA)
    c.setFont("Helvetica-Bold", 18)
    c.drawRightString(ancho - 20, y - 4, f"${cuota.monto:,}".replace(",", "."))

    y -= 50
    c.setStrokeColor(GRIS)
    c.setDash(2, 2)
    c.line(20, y, ancho - 20, y)
    c.setDash()
    y -= 20

    c.setFillColor(GRIS)
    c.setFont("Helvetica-Oblique", 7)
    generado = timezone.localtime().strftime("%d-%m-%Y %H:%M")
    c.drawString(20, y, "Comprobante generado digitalmente por")
    y -= 10
    c.drawString(20, y, f"SecurApp Copropiedad el {generado}.")
    y -= 11
    c.drawString(20, y, f"Código de verificación: {_codigo_verificacion(cuota)}")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()


def generar_boucher_pdf(cuota):
    """Para la descarga desde el navegador -- ver generar_boucher_pdf_bytes para el PDF en sí."""
    response = HttpResponse(generar_boucher_pdf_bytes(cuota), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{nombre_archivo_boucher(cuota)}"'
    return response


def enviar_boucher_por_correo(cuota, destinatario):
    """Correo con el comprobante a UN destinatario, elegido por quien marca la
    cuota como pagada -- a propósito no se manda automáticamente a todos los
    residentes de la unidad (puede haber más de una cuenta por depto, incluida
    la de un menor de edad, y no corresponde mandarle a todos un comprobante
    de pago). No bloquea el marcado como pagada si el correo falla (mismo
    criterio que enviar_correo_bienvenida en core/views.py)."""
    from core.views import EMAIL_CONTACTO_DEVQUAD

    condominio = cuota.gasto_comun.condominio
    try:
        correo = EmailMessage(
            subject=f"Comprobante de pago -- {condominio.etiqueta_unidad} {cuota.unidad.numero}, periodo {cuota.gasto_comun.periodo}",
            body=(
                f"Hola,\n\nAdjunto el comprobante de pago del gasto común de {condominio.nombre}, "
                f"periodo {cuota.gasto_comun.periodo}.\n\n"
                f"Cualquier duda, escríbenos a {EMAIL_CONTACTO_DEVQUAD}."
            ),
            from_email=None,
            to=[destinatario],
        )
        correo.attach(nombre_archivo_boucher(cuota), generar_boucher_pdf_bytes(cuota), "application/pdf")
        correo.send()
    except Exception:
        # destinatario llega validado como email real (validate_email en
        # MarcarCuotaPagadaView), pero igual se limpia de saltos de línea acá
        # -- un valor con \r/\n en el log podría falsificar líneas de log
        # ajenas (ver python:S6252/log injection en SonarCloud).
        destinatario_log = destinatario.replace("\r", "").replace("\n", "")
        logger.exception("No se pudo enviar el comprobante de pago a %s (cuota #%s).", destinatario_log, cuota.pk)

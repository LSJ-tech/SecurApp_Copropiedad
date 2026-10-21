from django.db import models

from core.models import PLAN_CHOICES, Condominio, Membresia

ESTADO_PAGO_CHOICES = [
    ("pendiente", "Pendiente"),
    ("aprobado", "Aprobado"),
    ("rechazado", "Rechazado"),
]

TIPO_PAGO_CHOICES = [
    ("suscripcion", "Suscripción"),
    ("donacion", "Donación"),
]

ESTADO_SUSCRIPCION_RECURRENTE_CHOICES = [
    ("pendiente", "Pendiente de autorizar"),
    ("autorizada", "Autorizada"),
    ("pausada", "Pausada"),
    ("cancelada", "Cancelada"),
]


class SuscripcionRecurrente(models.Model):
    """La autorización de cobro automático en Mercado Pago (API Preapproval,
    no Checkout Pro) -- se crea una vez, y Mercado Pago cobra el monto solo
    cada mes hasta que se cancele (ver cancelar_suscripcion_recurrente en
    mercadopago_client.py). Cada cobro exitoso genera un Pago nuevo
    (ver Pago.suscripcion_recurrente)."""

    condominio = models.ForeignKey(Condominio, on_delete=models.CASCADE, related_name="suscripciones_recurrentes")
    membresia = models.ForeignKey(
        Membresia, on_delete=models.SET_NULL, null=True, blank=True, related_name="donaciones_recurrentes",
        help_text="Quién donó -- vacío si es la suscripción del condominio como tal.",
    )
    tipo = models.CharField(max_length=15, choices=TIPO_PAGO_CHOICES, default="suscripcion")
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    mercadopago_preapproval_id = models.CharField(max_length=100, unique=True)
    estado = models.CharField(max_length=10, choices=ESTADO_SUSCRIPCION_RECURRENTE_CHOICES, default="pendiente")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_cancelacion = models.DateTimeField(null=True, blank=True)
    recordatorio_enviado_en = models.DateTimeField(
        null=True, blank=True,
        help_text="Cuándo se mandó el correo recordando autorizar una donación pendiente -- vacío si nunca se mandó. Evita repetirlo en cada sincronización.",
    )

    class Meta:
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"Suscripción recurrente #{self.pk} - {self.condominio} - {self.estado}"


class Pago(models.Model):
    """Un cobro -- de la suscripción SaaS (condominio -> DevQuad) o de una
    donación voluntaria (residente -> DevQuad), ver `tipo`. Desde que ambas
    pasaron a cobro automático recurrente (SuscripcionRecurrente), cada
    Pago representa un cobro individual dentro de ese ciclo, no un pago
    suelto -- no confundir con gastos comunes (residente -> su propio
    condominio, ver la app `gastoscomunes`, un flujo de dinero de terceros
    con mecanismo distinto, manual)."""

    condominio = models.ForeignKey(Condominio, on_delete=models.CASCADE, related_name="pagos")
    membresia = models.ForeignKey(
        Membresia, on_delete=models.SET_NULL, null=True, blank=True, related_name="donaciones",
        help_text="Quién donó (torre/unidad incluida) -- vacío en pagos de suscripción, que son del condominio como tal.",
    )
    suscripcion_recurrente = models.ForeignKey(
        SuscripcionRecurrente, on_delete=models.SET_NULL, null=True, blank=True, related_name="cobros",
        help_text="El cobro automático del que vino este pago.",
    )
    tipo = models.CharField(max_length=15, choices=TIPO_PAGO_CHOICES, default="suscripcion")
    plan = models.CharField(max_length=10, choices=PLAN_CHOICES, blank=True, help_text="Vacío si es una donación -- no está ligada a ningún plan.")
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=10, choices=ESTADO_PAGO_CHOICES, default="pendiente")
    mercadopago_payment_id = models.CharField(max_length=100, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_confirmacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"Pago #{self.pk} - {self.condominio} - {self.estado}"

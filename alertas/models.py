from django.db import models

from core.models import Condominio, Membresia

TIPO_CHOICES = [
    ("robo", "Robo"),
    ("incendio", "Incendio"),
    ("accidente", "Accidente"),
    ("otro", "Otro"),
    ("prueba", "Prueba"),
]

ESTADO_CHOICES = [
    ("activa", "Activa"),
    ("resuelta", "Resuelta"),
    ("falsa_alarma", "Falsa alarma"),
    ("auto_cerrada", "Cerrada automáticamente"),
]

MINUTOS_AUTO_CIERRE = 30


class Alerta(models.Model):
    condominio = models.ForeignKey(Condominio, on_delete=models.CASCADE, related_name="alertas")
    autor = models.ForeignKey(Membresia, on_delete=models.CASCADE, related_name="alertas_creadas")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default="otro")
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default="activa")
    mensaje = models.CharField(max_length=255, blank=True)
    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    resuelta_por = models.ForeignKey(Membresia, on_delete=models.SET_NULL, null=True, blank=True, related_name="alertas_resueltas")
    fecha_resolucion = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.condominio} ({self.fecha_creacion:%Y-%m-%d %H:%M})"

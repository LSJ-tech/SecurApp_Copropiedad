from django.contrib.auth.models import User
from django.db import models

from alertas.models import ESTADO_CHOICES, TIPO_CHOICES
from core.models import REGION_CHOICES

# Piloto acotado a estas 3 comunas (Región de Valparaíso) -- ampliar esta
# lista es la única forma de sumar cobertura, sin rediseño (ver
# RegistroVecinoForm.clean).
COMUNAS_PILOTO = ["Valparaíso", "Viña del Mar", "Casablanca"]

# Precisión de geohash usada para agrupar personas por "barrio" (~5km) --
# ver vecindario/services.py para el cálculo de celdas vecinas.
PRECISION_GEOHASH = 5


class PerfilGeografico(models.Model):
    """Perfil de la red vecinal geográfica -- independiente de Membresia
    a propósito (ver plan): una persona puede tener los dos a la vez, uno
    no reemplaza al otro. Nunca se asume condominio acá."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil_geografico")
    direccion_texto = models.CharField(max_length=255)
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lng = models.DecimalField(max_digits=9, decimal_places=6)
    region = models.CharField(max_length=100, choices=REGION_CHOICES)
    comuna = models.CharField(max_length=100)
    geohash = models.CharField(max_length=12, db_index=True)
    telefono = models.CharField(max_length=20, blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} ({self.comuna})"


class AlertaCiudadana(models.Model):
    """Alerta de la red vecinal geográfica -- separada de alertas.Alerta a
    propósito (no mezclar con la lógica condominio-céntrica existente).
    Reusa TIPO_CHOICES/ESTADO_CHOICES de alertas en vez de duplicarlos."""

    autor = models.ForeignKey(PerfilGeografico, on_delete=models.CASCADE, related_name="alertas_creadas")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="otro")
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default="activa")
    mensaje = models.CharField(max_length=255, blank=True)
    # Del momento de la alerta, no la dirección registrada -- alguien puede
    # estar fuera de su casa cuando pasa algo.
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lng = models.DecimalField(max_digits=9, decimal_places=6)
    geohash_momento = models.CharField(max_length=12, db_index=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    resuelta_por = models.ForeignKey(PerfilGeografico, on_delete=models.SET_NULL, null=True, blank=True, related_name="alertas_resueltas")
    fecha_resolucion = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.autor} ({self.fecha_creacion:%Y-%m-%d %H:%M})"

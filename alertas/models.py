from django.db import models

from core.models import Condominio, Membresia

TIPO_CHOICES = [
    ("robo", "Robo"),
    ("incendio", "Incendio"),
    ("accidente", "Accidente"),
    ("emergencia_medica", "Emergencia médica"),
    ("persona_extrana", "Persona extraña en el sector"),
    ("fuga_gas", "Fuga de gas"),
    ("fuga_agua", "Fuga o inundación de agua"),
    ("atrapado_ascensor", "Persona atrapada en ascensor"),
    ("objeto_sospechoso", "Objeto o paquete sospechoso"),
    ("rina_disturbio", "Riña o disturbio"),
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
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="otro")
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


CATEGORIA_NUMERO_CHOICES = [
    ("policia", "Policía/Carabineros"),
    ("bomberos", "Bomberos"),
    ("salud", "Salud/Ambulancia"),
    ("electricidad", "Electricidad"),
    ("agua", "Agua potable"),
    ("gas", "Gas"),
    ("otro", "Otro"),
]

# Los 4 únicos que se precargan solos (ver NumeroEmergenciaListView) --
# nacionales, estables y no dependen de la comuna. Todo lo demás (Plan
# Cuadrante, eléctrica, agua) varía por comuna -- a veces por sector dentro
# de la misma comuna -- así que lo agrega directiva/administración a mano
# con el número real de su condominio, nunca adivinado acá.
NUMEROS_NACIONALES = [
    ("policia", "Carabineros", "133"),
    ("bomberos", "Bomberos", "132"),
    ("salud", "Ambulancia (SAMU)", "131"),
    ("policia", "PDI", "134"),
]


class NumeroEmergencia(models.Model):
    """Directorio de teléfonos de emergencia del condominio."""

    condominio = models.ForeignKey(Condominio, on_delete=models.CASCADE, related_name="numeros_emergencia")
    categoria = models.CharField(max_length=15, choices=CATEGORIA_NUMERO_CHOICES, default="otro")
    nombre = models.CharField(max_length=100)
    telefono = models.CharField(max_length=30)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["categoria", "nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.telefono})"

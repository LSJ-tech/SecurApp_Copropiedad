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
    # Ya no se genera sola (se sacó el cierre automático a los 30 min --
    # daba una falsa sensación de que la emergencia ya se había atendido).
    # Se deja el choice solo para las alertas viejas que ya quedaron así.
    ("auto_cerrada", "Cerrada automáticamente"),
]


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
    ("apoyo", "Líneas de apoyo"),
    ("electricidad", "Electricidad"),
    ("agua", "Agua potable"),
    ("gas", "Gas"),
    ("otro", "Otro"),
]

# Los que se precargan solos (ver NumeroEmergenciaListView) -- nacionales,
# estables y no dependen de la comuna. Todo lo demás (Plan Cuadrante,
# eléctrica, agua) SÍ varía por comuna -- a veces por sector dentro de la
# misma comuna -- así que lo agrega directiva/administración a mano con el
# número real de su condominio, nunca adivinado acá.
#
# Confianza alta (código corto de 3 dígitos, históricamente estable, mismo
# valor en todas las fuentes consultadas): 130/131/132/133/134/147/149/1412.
# Confianza media (un solo número 600 confirmado por fuente, "conviene
# verificarlo" según la propia búsqueda): Salud Responde y SENAPRED --
# verificar en su sitio oficial si se quiere usar para algo crítico.
NUMEROS_NACIONALES = [
    ("policia", "Carabineros", "133"),
    ("policia", "PDI", "134"),
    ("bomberos", "Bomberos", "132"),
    ("bomberos", "CONAF (incendios forestales)", "130"),
    ("salud", "Ambulancia (SAMU)", "131"),
    ("salud", "Salud Responde", "600 360 7777"),
    ("apoyo", "Fono Familia (violencia intrafamiliar)", "149"),
    ("apoyo", "Fono Niños (PDI)", "147"),
    ("apoyo", "Fono Drogas y Alcohol (SENDA)", "1412"),
    ("apoyo", "SENAPRED (emergencias y desastres)", "600 586 7700"),
]

# Para saber si un NumeroEmergencia es nacional sin un campo de BD aparte
# (y sin necesitar backfill cuando se amplía NUMEROS_NACIONALES más
# adelante -- ver NumeroEmergencia.es_nacional).
_NOMBRES_NACIONALES = {nombre for _categoria, nombre, _telefono in NUMEROS_NACIONALES}


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

    @property
    def es_nacional(self):
        """Los nacionales (Carabineros, Bomberos, etc.) no se pueden borrar
        -- ver EliminarNumeroEmergenciaView. Calculado por nombre, no por un
        campo de BD aparte, así que no hace falta backfill cuando se agregan
        más nacionales (NumeroEmergenciaListView los vuelve a sincronizar
        solo en cada visita, ver su get_queryset)."""
        return self.nombre in _NOMBRES_NACIONALES


ESTADO_PROPUESTA_CHOICES = [
    ("pendiente", "Pendiente"),
    ("aprobada", "Aprobada"),
    ("rechazada", "Rechazada"),
]


class PropuestaNumeroEmergencia(models.Model):
    """Cualquier residente puede proponer un número regional (Plan
    Cuadrante, eléctrica, agua, etc. -- los nacionales son fijos y no
    admiten propuestas) -- directiva/administración lo aprueba o rechaza
    antes de que aparezca en la lista real (NumeroEmergencia). Mismo
    cuidado que con las sugerencias por región: nadie más que directiva/
    administración decide qué número queda visible para todo el
    condominio sin revisión."""

    condominio = models.ForeignKey(Condominio, on_delete=models.CASCADE, related_name="propuestas_numero_emergencia")
    autor = models.ForeignKey(Membresia, on_delete=models.CASCADE, related_name="propuestas_numero_emergencia")
    categoria = models.CharField(max_length=15, choices=CATEGORIA_NUMERO_CHOICES, default="otro")
    nombre = models.CharField(max_length=100)
    telefono = models.CharField(max_length=30)
    nota = models.CharField(max_length=255, blank=True, help_text="Opcional -- para qué sirve o por qué lo propones.")
    estado = models.CharField(max_length=10, choices=ESTADO_PROPUESTA_CHOICES, default="pendiente")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    revisada_por = models.ForeignKey(Membresia, on_delete=models.SET_NULL, null=True, blank=True, related_name="propuestas_revisadas")
    fecha_revision = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"{self.nombre} ({self.get_estado_display()})"


class AlertaLectura(models.Model):
    """Quién vio cada alerta -- base de "visto por X vecinos", visible
    solo para el propio autor (ver AlertaSerializer.get_visto_por_count).
    Se registra con una acción explícita (marcar_visto), nunca pasiva."""

    alerta = models.ForeignKey(Alerta, on_delete=models.CASCADE, related_name="lecturas")
    membresia = models.ForeignKey(Membresia, on_delete=models.CASCADE, related_name="alertas_vistas")
    fecha_lectura = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["alerta", "membresia"], name="lectura_unica_por_alerta_y_membresia"),
        ]

    def __str__(self):
        return f"{self.membresia} vio la alerta #{self.alerta_id}"

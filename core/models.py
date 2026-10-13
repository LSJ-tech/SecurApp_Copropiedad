import datetime
import uuid

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .usuarios import generar_codigo_invitacion

REGION_CHOICES = [
    ("arica_parinacota", "Arica y Parinacota"),
    ("tarapaca", "Tarapacá"),
    ("antofagasta", "Antofagasta"),
    ("atacama", "Atacama"),
    ("coquimbo", "Coquimbo"),
    ("valparaiso", "Valparaíso"),
    ("metropolitana", "Metropolitana de Santiago"),
    ("ohiggins", "Libertador General Bernardo O'Higgins"),
    ("maule", "Maule"),
    ("nuble", "Ñuble"),
    ("biobio", "Biobío"),
    ("araucania", "La Araucanía"),
    ("los_rios", "Los Ríos"),
    ("los_lagos", "Los Lagos"),
    ("aysen", "Aysén del General Carlos Ibáñez del Campo"),
    ("magallanes", "Magallanes y de la Antártica Chilena"),
]

PLAN_CHOICES = [
    ("free", "Gratis"),
    ("premium", "Pro"),
]

ROL_CHOICES = [
    ("directiva", "Directiva"),
    ("administracion", "Administración"),
    ("conserje", "Conserjería"),
    ("residente", "Residente"),
]

GENERO_UNIDAD_CHOICES = [
    ("f", "Femenino (la/una/nueva unidad)"),
    ("m", "Masculino (el/un/nuevo departamento)"),
]

DIAS_PRUEBA_GRATIS = 20


def _pagado_hasta_prueba_gratis():
    """20 días de prueba gratis del sistema de gestión (gastos comunes y
    personal/liquidaciones) para cualquier condominio nuevo -- mismo campo
    que ya usa SuscripcionActivaMixin, sin lógica de trial aparte. Se aplica
    tanto al registro self-service como a un alta manual (Django admin,
    management command) que no fije pagado_hasta explícito."""
    return timezone.localdate() + datetime.timedelta(days=DIAS_PRUEBA_GRATIS)


class Condominio(models.Model):
    """El tenant: una junta de vecinos o condominio cliente de la plataforma.

    A diferencia de PataAgenda (Negocio + Sucursal), acá hay un solo nivel de
    tenant -- alertas, avisos, conserjería y gastos comunes son compartidos
    por todo el condominio, no por torre.
    """

    nombre = models.CharField(max_length=150)
    etiqueta_organizacion = models.CharField(
        max_length=30, default="Condominio",
        help_text="Cómo le dicen a esta organización (Condominio, Junta de vecinos, Comunidad, Villa...) -- "
        "se usa en el panel en frases como 'Mi Condominio'/'Mi Junta de vecinos', en vez de 'Mi condominio' a secas.",
    )
    direccion = models.CharField(
        max_length=255, blank=True, verbose_name="dirección o sector",
        help_text="No tiene que ser una dirección exacta -- una junta de vecinos suele cubrir varias calles. "
        "Puede ser una descripción tipo \"Sector Los Aromos\" o \"Entre Av. Principal y Los Olivos\".",
    )
    comuna = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    activo = models.BooleanField(default=True, help_text="Interruptor manual: desactivarlo bloquea todo (ej. un cliente que dejó de serlo).")
    plan = models.CharField(max_length=10, choices=PLAN_CHOICES, default="premium", help_text="Legado -- hoy el precio es fijo ($19.990/mes, ver README), este campo es solo registro interno de DevQuad y no limita nada.")
    pagado_hasta = models.DateField(
        null=True, blank=True, default=_pagado_hasta_prueba_gratis,
        help_text=f"Hasta cuándo puede generar gastos comunes/personal nuevos sin pagar (ver SuscripcionActivaMixin) -- "
        f"{DIAS_PRUEBA_GRATIS} días de prueba gratis al crear el condominio, después hay que pagar la suscripción. "
        "El resto de la app (alertas, avisos, accesos) nunca depende de este campo.",
    )
    es_fundador = models.BooleanField(default=False, help_text="Uno de los primeros condominios en registrarse.")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    datos_transferencia = models.TextField(
        blank=True,
        help_text="Banco, tipo de cuenta, número, RUT y email de la administración — se muestra a los "
        "residentes para que paguen los gastos comunes por transferencia (no es un pago online).",
    )
    token_registro_residentes = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False,
        help_text="Identifica el link/QR público de autoregistro de residentes de este condominio.",
    )
    etiqueta_torre = models.CharField(
        max_length=30, default="Torre",
        help_text="Cómo le dicen en este condominio a la agrupación de unidades (Torre, Block, Edificio, "
        "Pabellón...) -- se usa tal cual en el panel, en vez de 'Torre' a secas.",
    )
    etiqueta_unidad = models.CharField(
        max_length=30, default="Unidad",
        help_text="Cómo le dicen en este condominio a cada unidad (Unidad, Departamento, Casa...) -- "
        "se usa tal cual en el panel, en vez de 'Unidad'/'Depto' a secas.",
    )
    genero_unidad = models.CharField(
        max_length=1, choices=GENERO_UNIDAD_CHOICES, default="f",
        help_text="Solo para que el texto concuerde en género con etiqueta_unidad (ej. 'nueva unidad' vs "
        "'nuevo departamento'). No afecta nada más.",
    )
    condominios_vecinos = models.ManyToManyField(
        "self", blank=True,
        help_text="Otros condominios/juntas de vecinos con los que se comparten las alertas de pánico "
        "porque son del mismo vecindario (se ven y se avisan entre sí). Al agregar uno, queda vinculado "
        "en ambos sentidos automáticamente. Todo lo demás -- miembros, gastos comunes, torres/unidades, "
        "avisos, accesos -- sigue completamente separado por condominio.",
    )

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    @property
    def esta_vencido(self):
        return self.pagado_hasta is not None and self.pagado_hasta < timezone.localdate()

    @property
    def puede_operar(self):
        """El precio es fijo y la cobranza manual (ver README) -- no hay
        corte automático por falta de pago. Lo único que puede bloquear el
        acceso es el interruptor manual `activo` (ver su help_text)."""
        return self.activo

    @property
    def total_unidades(self):
        return self.unidades.count()

    @property
    def total_torres(self):
        return self.torres.count()

    @property
    def ids_red_alertas(self):
        """IDs del propio condominio + sus condominios_vecinos -- para que
        las alertas de pánico (y solo ellas) se compartan dentro del
        vecindario sin tocar el aislamiento del resto de los datos."""
        return [self.pk] + list(self.condominios_vecinos.values_list("pk", flat=True))

    @property
    def etiqueta_unidad_nueva(self):
        """'Nueva unidad' / 'Nuevo departamento' -- concuerda en género con etiqueta_unidad."""
        return "Nuevo" if self.genero_unidad == "m" else "Nueva"

    @property
    def etiqueta_unidad_todos(self):
        """'TODAS las unidades' / 'TODOS los departamentos' -- idem, para el plural."""
        return "TODOS los" if self.genero_unidad == "m" else "TODAS las"


class Torre(models.Model):
    """Agrupación organizativa opcional dentro de un condominio grande -- NO es un tenant."""

    condominio = models.ForeignKey(Condominio, on_delete=models.CASCADE, related_name="torres")
    nombre = models.CharField(max_length=100)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.condominio})"


class Unidad(models.Model):
    """Un departamento/casa dentro del condominio -- nivel al que se prorratean los gastos comunes."""

    condominio = models.ForeignKey(Condominio, on_delete=models.CASCADE, related_name="unidades")
    torre = models.ForeignKey(Torre, on_delete=models.SET_NULL, null=True, blank=True, related_name="unidades")
    numero = models.CharField(max_length=20, help_text="Número o identificador del departamento/casa, ej. '304' o 'Casa 12'.")
    calle = models.CharField(
        max_length=150, blank=True,
        help_text="Nombre de la calle -- útil si la junta de vecinos tiene varias calles y un mismo número de "
        "casa podría repetirse en más de una. Vacío si no aplica (ej. torres/deptos, o juntas con una sola calle).",
    )
    alicuota = models.DecimalField(max_digits=6, decimal_places=4, default=0, help_text="Coeficiente de copropiedad usado para prorratear gastos comunes (0 si no se usa).")

    class Meta:
        ordering = ["numero"]
        constraints = [
            models.UniqueConstraint(fields=["condominio", "torre", "numero"], name="unidad_numero_unico_por_torre"),
        ]

    def __str__(self):
        if self.torre_id:
            return f"Torre {self.torre.nombre} - Depto {self.numero}"
        if self.calle:
            return f"{self.calle} {self.numero} - {self.condominio}"
        return f"{self.numero} - {self.condominio}"


class Membresia(models.Model):
    """Liga un usuario de login a su condominio y le asigna un rol."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="membresia")
    condominio = models.ForeignKey(Condominio, on_delete=models.CASCADE, related_name="membresias")
    unidad = models.ForeignKey(Unidad, on_delete=models.SET_NULL, null=True, blank=True, related_name="membresias", help_text="Obligatoria para residentes. No aplica a directiva/administración/conserjería.")
    rol = models.CharField(max_length=15, choices=ROL_CHOICES, default="residente")
    terminos_aceptados_en = models.DateTimeField(
        null=True, blank=True,
        help_text="Cuándo esta persona aceptó los Términos de Uso y la Política de Privacidad. Vacío = todavía no los ha aceptado.",
    )

    def __str__(self):
        return f"{self.user} ({self.get_rol_display()} de {self.condominio})"

    def clean(self):
        super().clean()
        if self.rol == "residente" and self.unidad_id is None:
            raise ValidationError({"unidad": "Las cuentas de residente deben tener una unidad asignada."})
        if self.unidad_id and self.condominio_id and self.unidad.condominio_id != self.condominio_id:
            raise ValidationError({"unidad": "La unidad debe pertenecer al mismo condominio de la membresía."})


class CodigoInvitacion(models.Model):
    """Gate del registro público: sin un código válido y no usado, no se puede crear un condominio."""

    codigo = models.CharField(max_length=20, unique=True, default=generar_codigo_invitacion)
    condominio = models.OneToOneField(Condominio, on_delete=models.CASCADE, null=True, blank=True, related_name="codigo_invitacion")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_uso = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return self.codigo

    @property
    def usado(self):
        return self.condominio_id is not None


class SolicitudAcceso(models.Model):
    """Lead capturado desde el formulario público de la landing -- quien lo pide todavía no tiene código de invitación."""

    nombre = models.CharField(max_length=150)
    condominio = models.CharField(max_length=150, verbose_name="Condominio o junta de vecinos")
    comuna = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    mensaje = models.TextField(blank=True)
    atendido = models.BooleanField(default=False, help_text="Marca cuando ya contactaste a esta persona.")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"{self.condominio} ({self.nombre})"


class SolicitudEliminacion(models.Model):
    """Pedido de un miembro de eliminar su cuenta y sus datos personales (derecho de
    cancelación/eliminación). No borra nada solo -- queda registrada para que DevQuad
    la procese manualmente (ver también el correo que se envía al crearla)."""

    membresia = models.ForeignKey(
        Membresia, on_delete=models.SET_NULL, null=True, blank=True, related_name="solicitudes_eliminacion",
        help_text="Puede quedar vacío si la cuenta ya fue eliminada -- los campos de abajo son una copia al momento del pedido.",
    )
    nombre = models.CharField(max_length=150)
    username = models.CharField(max_length=150)
    condominio_nombre = models.CharField(max_length=150)
    motivo = models.TextField(blank=True)
    atendida = models.BooleanField(default=False, help_text="Marca cuando ya se procesó la eliminación.")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_atencion = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"{self.nombre} ({self.username}) - {self.condominio_nombre}"

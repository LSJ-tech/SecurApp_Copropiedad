from django.db import models

from core.models import Condominio, Membresia


class Aviso(models.Model):
    condominio = models.ForeignKey(Condominio, on_delete=models.CASCADE, related_name="avisos")
    autor = models.ForeignKey(Membresia, on_delete=models.CASCADE, related_name="avisos")
    titulo = models.CharField(max_length=150)
    cuerpo = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return self.titulo


class AvisoLectura(models.Model):
    """Quién vio cada aviso -- base de "Visto por X de Y vecinos" en el
    serializer, visible solo para directiva/administración (ver
    AvisoSerializer.get_leido_por_count)."""

    aviso = models.ForeignKey(Aviso, on_delete=models.CASCADE, related_name="lecturas")
    membresia = models.ForeignKey(Membresia, on_delete=models.CASCADE, related_name="avisos_leidos")
    fecha_lectura = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["aviso", "membresia"], name="lectura_unica_por_aviso_y_membresia"),
        ]

    def __str__(self):
        return f"{self.membresia} leyó «{self.aviso.titulo}»"

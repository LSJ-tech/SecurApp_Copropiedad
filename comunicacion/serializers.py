from typing import Optional

from rest_framework import serializers

from core.models import Membresia

from .models import Aviso


class AvisoSerializer(serializers.ModelSerializer):
    autor_nombre = serializers.CharField(source="autor.user.get_full_name", read_only=True, default=None)
    torre_nombre = serializers.CharField(source="torre.nombre", read_only=True, default=None)
    leido_por_count = serializers.SerializerMethodField()
    total_destinatarios = serializers.SerializerMethodField()

    class Meta:
        model = Aviso
        fields = [
            "id", "titulo", "cuerpo", "fecha_creacion", "autor_nombre", "torre_nombre",
            "leido_por_count", "total_destinatarios",
        ]

    def _puede_ver_estadisticas(self):
        """Solo devquad ve cuántos vecinos vieron el aviso -- a un residente
        no le aporta nada y solo ensucia la tarjeta."""
        request = self.context.get("request")
        return bool(request and request.user.is_staff)

    def get_leido_por_count(self, obj) -> Optional[int]:
        if not self._puede_ver_estadisticas():
            return None
        return obj.lecturas.count()

    def get_total_destinatarios(self, obj) -> Optional[int]:
        if not self._puede_ver_estadisticas():
            return None
        qs = Membresia.objects.filter(condominio_id=obj.condominio_id)
        if obj.torre_id:
            qs = qs.filter(unidad__torre_id=obj.torre_id)
        return qs.count()

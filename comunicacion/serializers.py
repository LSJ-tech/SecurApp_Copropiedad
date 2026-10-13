from typing import Optional

from rest_framework import serializers

from core.models import Membresia

from .models import Aviso, Publicacion


class AvisoSerializer(serializers.ModelSerializer):
    autor_nombre = serializers.CharField(source="autor.user.get_full_name", read_only=True)
    leido_por_count = serializers.SerializerMethodField()
    total_destinatarios = serializers.SerializerMethodField()

    class Meta:
        model = Aviso
        fields = ["id", "titulo", "cuerpo", "fecha_creacion", "autor_nombre", "leido_por_count", "total_destinatarios"]

    def _puede_ver_estadisticas(self):
        """Solo directiva/administración ven cuántos vecinos vieron el aviso
        -- a un residente no le aporta nada y solo ensucia la tarjeta."""
        request = self.context.get("request")
        membresia = getattr(request.user, "membresia", None) if request else None
        return bool(membresia and membresia.rol in ("directiva", "administracion"))

    def get_leido_por_count(self, obj) -> Optional[int]:
        if not self._puede_ver_estadisticas():
            return None
        return obj.lecturas.count()

    def get_total_destinatarios(self, obj) -> Optional[int]:
        if not self._puede_ver_estadisticas():
            return None
        return Membresia.objects.filter(condominio_id=obj.condominio_id).count()


class PublicacionSerializer(serializers.ModelSerializer):
    autor_nombre = serializers.CharField(source="autor.user.get_full_name", read_only=True)
    autor_unidad = serializers.CharField(source="autor.unidad.numero", read_only=True, default=None)
    autor_torre = serializers.CharField(source="autor.unidad.torre.nombre", read_only=True, default=None)
    categoria_display = serializers.CharField(source="get_categoria_display", read_only=True)
    puede_eliminar = serializers.SerializerMethodField()
    torre_nombre = serializers.CharField(source="torre.nombre", read_only=True, default=None)
    # Nunca se expone "torre" en sí (elegir una ajena a la propia no tendría
    # sentido) -- solo este booleano; PublicacionViewSet.perform_create
    # resuelve la torre real a partir de la del autor.
    solo_mi_torre = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = Publicacion
        fields = [
            "id", "categoria", "categoria_display", "titulo", "cuerpo", "fecha_creacion",
            "autor_nombre", "autor_unidad", "autor_torre", "puede_eliminar", "torre_nombre", "solo_mi_torre",
        ]

    def get_puede_eliminar(self, obj) -> bool:
        """El autor siempre puede borrar lo suyo; directiva/administración
        pueden moderar lo de cualquiera (es un muro abierto a todos)."""
        request = self.context.get("request")
        membresia = getattr(request.user, "membresia", None) if request else None
        if not membresia:
            return False
        return bool(obj.autor_id == membresia.id or membresia.rol in ("directiva", "administracion"))

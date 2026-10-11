from rest_framework import serializers

from .models import Alerta


class AlertaSerializer(serializers.ModelSerializer):
    autor_nombre = serializers.CharField(source="autor.user.get_full_name", read_only=True)
    autor_unidad = serializers.CharField(source="autor.unidad.numero", read_only=True, default=None)
    autor_torre = serializers.CharField(source="autor.unidad.torre.nombre", read_only=True, default=None)
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    resuelta_por_nombre = serializers.CharField(source="resuelta_por.user.get_full_name", read_only=True, default=None)
    resuelta_por_unidad = serializers.CharField(source="resuelta_por.unidad.numero", read_only=True, default=None)
    condominio_nombre = serializers.CharField(source="condominio.nombre", read_only=True)

    class Meta:
        model = Alerta
        fields = [
            "id", "condominio_nombre", "tipo", "tipo_display", "estado", "estado_display",
            "mensaje", "latitud", "longitud", "fecha_creacion", "autor_nombre", "autor_unidad", "autor_torre",
            "resuelta_por", "resuelta_por_nombre", "resuelta_por_unidad", "fecha_resolucion",
        ]
        read_only_fields = ["estado", "resuelta_por", "fecha_resolucion"]

from rest_framework import serializers

from .models import AlertaCiudadana


class AlertaCiudadanaSerializer(serializers.ModelSerializer):
    autor_nombre = serializers.CharField(source="autor.user.get_full_name", read_only=True)
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)

    class Meta:
        model = AlertaCiudadana
        fields = [
            "id", "tipo", "tipo_display", "estado", "estado_display", "mensaje",
            "lat", "lng", "fecha_creacion", "autor_nombre", "resuelta_por", "fecha_resolucion",
        ]
        read_only_fields = ["estado", "resuelta_por", "fecha_resolucion"]

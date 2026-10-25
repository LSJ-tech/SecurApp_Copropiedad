from typing import Optional

from rest_framework import serializers

from .models import CATEGORIA_NUMERO_CHOICES, Alerta, NumeroEmergencia, PropuestaNumeroEmergencia


class AlertaSerializer(serializers.ModelSerializer):
    autor_nombre = serializers.CharField(source="autor.user.get_full_name", read_only=True)
    autor_unidad = serializers.CharField(source="autor.unidad.numero", read_only=True, default=None)
    autor_torre = serializers.CharField(source="autor.unidad.torre.nombre", read_only=True, default=None)
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    resuelta_por_nombre = serializers.CharField(source="resuelta_por.user.get_full_name", read_only=True, default=None)
    resuelta_por_unidad = serializers.CharField(source="resuelta_por.unidad.numero", read_only=True, default=None)
    condominio_nombre = serializers.CharField(source="condominio.nombre", read_only=True)
    visto_por_count = serializers.SerializerMethodField()

    class Meta:
        model = Alerta
        fields = [
            "id", "condominio_nombre", "tipo", "tipo_display", "estado", "estado_display",
            "mensaje", "latitud", "longitud", "fecha_creacion", "autor_nombre", "autor_unidad", "autor_torre",
            "resuelta_por", "resuelta_por_nombre", "resuelta_por_unidad", "fecha_resolucion", "visto_por_count",
        ]
        read_only_fields = ["estado", "resuelta_por", "fecha_resolucion"]

    def get_visto_por_count(self, obj) -> Optional[int]:
        """Visible solo para el propio autor de la alerta -- es reaseguro
        personal ("ya vieron tu alerta"), no una métrica para cualquiera.
        Usa la anotación del queryset (AlertaViewSet.queryset), no una
        consulta por fila -- evita N+1 al listar."""
        request = self.context.get("request")
        if not (request and request.user.id == obj.autor.user_id):
            return None
        count = getattr(obj, "visto_por_count_anotado", None)
        if count is not None:
            return count
        # Instancia recién creada (CreateModelMixin serializa el objeto
        # devuelto por .save(), no uno vuelto a traer por get_queryset() --
        # no lleva la anotación). Siempre 0 en ese caso, pero se calcula
        # igual en vez de asumirlo.
        return obj.lecturas.filter(membresia__condominio_id=obj.condominio_id).count()


class NumeroEmergenciaSerializer(serializers.ModelSerializer):
    categoria_display = serializers.CharField(source="get_categoria_display", read_only=True)

    class Meta:
        model = NumeroEmergencia
        fields = ["id", "categoria", "categoria_display", "nombre", "telefono", "es_nacional"]
        read_only_fields = fields


class PropuestaNumeroEmergenciaSerializer(serializers.ModelSerializer):
    # El modelo tiene default="otro" en categoria, lo que haría que
    # ModelSerializer la marque como no requerida -- a diferencia de
    # PropuestaNumeroEmergenciaForm (Django ModelForm) en la web, que sí la
    # exige. Se declara explícita para igualar esa validación.
    categoria = serializers.ChoiceField(choices=CATEGORIA_NUMERO_CHOICES, required=True)
    categoria_display = serializers.CharField(source="get_categoria_display", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)

    class Meta:
        model = PropuestaNumeroEmergencia
        fields = ["id", "categoria", "categoria_display", "nombre", "telefono", "nota", "estado", "estado_display", "fecha_creacion"]
        read_only_fields = ["estado"]

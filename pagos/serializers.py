from rest_framework import serializers

from .models import Pago, SuscripcionRecurrente


class PagoResumenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pago
        fields = ["monto", "estado", "fecha_creacion"]


class DonacionActualSerializer(serializers.ModelSerializer):
    class Meta:
        model = SuscripcionRecurrente
        fields = ["estado", "monto", "fecha_creacion"]

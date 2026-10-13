from django.conf import settings
from django.core.management.base import BaseCommand

from pagos.models import SuscripcionRecurrente
from pagos.views import sincronizar_estado_suscripcion


class Command(BaseCommand):
    help = (
        "Respaldo del webhook de Mercado Pago (que no ha llegado de forma confiable para "
        "transacciones reales -- ver pagos/views.py): re-consulta cada SuscripcionRecurrente no "
        "cancelada contra la API de Mercado Pago, igual que el botón 'Sincronizar con Mercado Pago' "
        "del admin, pero para todas a la vez. Pensado para correr periódico (Render Cron Job)."
    )

    def handle(self, *args, **options):
        if not settings.MERCADOPAGO_ACCESS_TOKEN:
            self.stdout.write("MERCADOPAGO_ACCESS_TOKEN no está configurado -- nada que sincronizar.")
            return

        suscripciones = SuscripcionRecurrente.objects.exclude(estado="cancelada")
        sincronizadas, fallidas = 0, 0
        for suscripcion in suscripciones:
            if sincronizar_estado_suscripcion(suscripcion):
                sincronizadas += 1
            else:
                fallidas += 1
                self.stdout.write(self.style.ERROR(f"No se pudo consultar la suscripción recurrente #{suscripcion.pk} en Mercado Pago."))

        self.stdout.write(self.style.SUCCESS(f"Sincronizadas {sincronizadas} suscripción(es), {fallidas} fallida(s)."))

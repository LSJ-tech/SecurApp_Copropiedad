from django.core.management.base import BaseCommand
from django.utils import timezone

from pagos.mercadopago_client import cancelar_suscripcion_recurrente
from pagos.models import SuscripcionRecurrente


class Command(BaseCommand):
    help = (
        "Cancela en Mercado Pago TODAS las SuscripcionRecurrente de tipo "
        "'suscripcion' (el cobro del condominio como cliente, no las "
        "donaciones) que sigan en estado pendiente/autorizada -- parte del "
        "retiro del modulo de gastos comunes/personal/accesos (ver memoria "
        "del proyecto). Por defecto es un dry-run: solo lista que "
        "cancelaria. Agregar --aplicar para cancelarlas de verdad contra "
        "la API real de Mercado Pago. NUNCA se corre sola (no esta en "
        "build.sh ni en ningun cron) -- es una accion deliberada, manual."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--aplicar", action="store_true",
            help="Sin esto, solo se listan las suscripciones -- no se cancela nada.",
        )

    def handle(self, *args, **options):
        aplicar = options["aplicar"]
        suscripciones = SuscripcionRecurrente.objects.filter(
            tipo="suscripcion", estado__in=["pendiente", "autorizada"],
        ).select_related("condominio").order_by("condominio__nombre")

        if not suscripciones:
            self.stdout.write("No hay ninguna suscripción de condominio activa que cancelar.")
            return

        self.stdout.write(f"{suscripciones.count()} suscripción(es) de condominio activa(s):")
        for suscripcion in suscripciones:
            self.stdout.write(
                f"  #{suscripcion.pk} | {suscripcion.condominio.nombre} | estado={suscripcion.estado} | "
                f"monto={suscripcion.monto} | preapproval_id={suscripcion.mercadopago_preapproval_id}"
            )

        if not aplicar:
            self.stdout.write(self.style.WARNING(
                "Dry-run -- no se canceló nada. Revisa la lista de arriba y vuelve a "
                "correr con --aplicar para cancelar de verdad en Mercado Pago."
            ))
            return

        canceladas, fallidas = 0, 0
        for suscripcion in suscripciones:
            if cancelar_suscripcion_recurrente(suscripcion):
                suscripcion.estado = "cancelada"
                suscripcion.fecha_cancelacion = timezone.now()
                suscripcion.save(update_fields=["estado", "fecha_cancelacion"])
                canceladas += 1
                self.stdout.write(self.style.SUCCESS(f"Cancelada #{suscripcion.pk} ({suscripcion.condominio.nombre})."))
            else:
                fallidas += 1
                self.stdout.write(self.style.ERROR(f"No se pudo cancelar #{suscripcion.pk} ({suscripcion.condominio.nombre}) -- revisar a mano."))

        self.stdout.write(self.style.SUCCESS(f"Listo. Canceladas: {canceladas}. Fallidas: {fallidas}."))

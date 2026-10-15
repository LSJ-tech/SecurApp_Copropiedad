import pygeohash as pgh
from django.core.management.base import BaseCommand

from core.models import Condominio
from vecindario.models import PRECISION_GEOHASH, PerfilGeografico
from vecindario.services import geocodificar_direccion, region_de_comuna


class Command(BaseCommand):
    """Suma a la red vecinal geográfica a los vecinos que ya están en
    condominios existentes (ej. Población EMPART), sin que tengan que
    volver a registrarse. Por cada Condominio sin procesar, geocodifica su
    dirección UNA vez y crea un PerfilGeografico para cada Membresia que
    todavía no tenga uno, heredando esa ubicación.

    No es una migración de Django a propósito -- depende de red (Nominatim)
    y no debe correr sola en cada deploy (ver la lección ya documentada en
    la memoria del proyecto sobre crear_condominio_empart/build.sh). Se
    corre a mano, con --aplicar para ejecutar de verdad (por defecto es
    dry-run)."""

    help = "Crea PerfilGeografico para los miembros de condominios existentes, geocodificando la dirección del condominio."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Ejecuta de verdad. Sin esto, solo reporta qué haría.")

    def handle(self, *args, **options):
        aplicar = options["aplicar"]
        condominios_sin_geocodificar = []
        perfiles_creados = 0
        condominios_procesados = 0

        for condominio in Condominio.objects.all():
            membresias_sin_perfil = condominio.membresias.filter(user__perfil_geografico__isnull=True)
            if not membresias_sin_perfil.exists():
                continue

            direccion = f"{condominio.direccion}, {condominio.comuna}".strip(", ")
            if not direccion:
                condominios_sin_geocodificar.append((condominio, "sin dirección/comuna registrada"))
                continue

            resultado = geocodificar_direccion(direccion)
            if not resultado:
                condominios_sin_geocodificar.append((condominio, "Nominatim no reconoció la dirección"))
                continue

            region = region_de_comuna(resultado["comuna"])
            if not region:
                condominios_sin_geocodificar.append((condominio, f"comuna {resultado['comuna']!r} no está en nuestros datos oficiales"))
                continue

            geohash = pgh.encode(resultado["lat"], resultado["lng"], precision=PRECISION_GEOHASH)
            condominios_procesados += 1

            for membresia in membresias_sin_perfil:
                self.stdout.write(f"  {condominio.nombre}: {membresia.user.get_full_name() or membresia.user.username} -> {resultado['comuna']}")
                if aplicar:
                    PerfilGeografico.objects.create(
                        user=membresia.user, direccion_texto=direccion, lat=resultado["lat"], lng=resultado["lng"],
                        region=region, comuna=resultado["comuna"], geohash=geohash,
                    )
                perfiles_creados += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Condominios geocodificados: {condominios_procesados}"))
        self.stdout.write(self.style.SUCCESS(f"Perfiles {'creados' if aplicar else 'a crear'}: {perfiles_creados}"))
        if condominios_sin_geocodificar:
            self.stdout.write(self.style.WARNING(f"Condominios sin procesar ({len(condominios_sin_geocodificar)}), revisar a mano:"))
            for condominio, motivo in condominios_sin_geocodificar:
                self.stdout.write(self.style.WARNING(f"  - {condominio.nombre}: {motivo}"))
        if not aplicar:
            self.stdout.write("")
            self.stdout.write(self.style.NOTICE("Esto fue un dry-run. Corre con --aplicar para crear los perfiles de verdad."))

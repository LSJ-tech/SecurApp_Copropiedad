"""Consolida Puesta del Sol (id=3) y Sofanor Parra (id=4) dentro de Empart
(id=1) -- ver plan "Consolidar 3 condominios en 1 (Empart)". Verificado
contra produccion (Supabase) antes de escribir esto: ambos son un solo
residente, una sola Unidad sin torre, cero alertas/avisos/pagos cada uno
-- son casas de la misma comunidad de Empart, no clientes aparte.

No recrea nada: re-apunta las Unidad/Membresia existentes (ids 653/654) a
Empart, y borra los 2 condominios vacios al final. Todo dentro de una
transaccion atomica.

Uso: DATABASE_URL se toma de .env.migracion (DATABASE_URL_DESTINO).
    venv/Scripts/python.exe scripts/consolidar_empart.py
"""
import os
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ENV_MIGRACION = RAIZ / ".env.migracion"

EMPART_ID = 1
PUESTA_DEL_SOL_ID = 3
SOFANOR_PARRA_ID = 4
USERNAME_ANDRES = "asanchez"
USERNAME_ADELA = "aserey"
UNIDAD_ANDRES_ID = 653
UNIDAD_ADELA_ID = 654


def leer_database_url_destino():
    if not ENV_MIGRACION.exists():
        sys.exit(f"Falta {ENV_MIGRACION.name} en la raíz del proyecto.")
    for linea in ENV_MIGRACION.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea.startswith("DATABASE_URL_DESTINO="):
            return linea.partition("=")[2].strip()
    sys.exit("Falta DATABASE_URL_DESTINO en .env.migracion")


def imprimir_conteos(Condominio, Torre, Unidad, Membresia):
    from alertas.models import Alerta
    from comunicacion.models import Aviso
    from pagos.models import Pago, SuscripcionRecurrente

    for pk in (EMPART_ID, PUESTA_DEL_SOL_ID, SOFANOR_PARRA_ID):
        c = Condominio.objects.filter(pk=pk).first()
        if c is None:
            print(f"  id={pk}: (ya no existe)")
            continue
        print(
            f"  id={pk} {c.nombre!r}: "
            f"torres={Torre.objects.filter(condominio=c).count()} "
            f"unidades={Unidad.objects.filter(condominio=c).count()} "
            f"membresias={Membresia.objects.filter(condominio=c).count()} "
            f"alertas={Alerta.objects.filter(condominio=c).count()} "
            f"avisos={Aviso.objects.filter(condominio=c).count()} "
            f"pagos={Pago.objects.filter(membresia__condominio=c).count()} "
            f"suscripciones={SuscripcionRecurrente.objects.filter(membresia__condominio=c).count()}"
        )


def main():
    os.environ["DATABASE_URL"] = leer_database_url_destino()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    sys.path.insert(0, str(RAIZ))
    import django
    django.setup()

    from django.db import transaction
    from core.models import Condominio, Membresia, Torre, Unidad

    print("-- Conteos antes de tocar nada:")
    imprimir_conteos(Condominio, Torre, Unidad, Membresia)

    with transaction.atomic():
        actualizadas_unidad = Unidad.objects.filter(pk=UNIDAD_ANDRES_ID).update(condominio_id=EMPART_ID)
        actualizadas_unidad += Unidad.objects.filter(pk=UNIDAD_ADELA_ID).update(condominio_id=EMPART_ID)
        actualizadas_membresia = Membresia.objects.filter(user__username=USERNAME_ANDRES).update(condominio_id=EMPART_ID)
        actualizadas_membresia += Membresia.objects.filter(user__username=USERNAME_ADELA).update(condominio_id=EMPART_ID)
        print(f"\n-- Movidas {actualizadas_unidad} unidad(es) y {actualizadas_membresia} membresía(s) a Empart.")

        for pk in (PUESTA_DEL_SOL_ID, SOFANOR_PARRA_ID):
            c = Condominio.objects.get(pk=pk)
            from alertas.models import Alerta
            from comunicacion.models import Aviso
            from pagos.models import Pago, SuscripcionRecurrente

            quedan = {
                "torres": Torre.objects.filter(condominio=c).count(),
                "unidades": Unidad.objects.filter(condominio=c).count(),
                "membresias": Membresia.objects.filter(condominio=c).count(),
                "alertas": Alerta.objects.filter(condominio=c).count(),
                "avisos": Aviso.objects.filter(condominio=c).count(),
                "pagos": Pago.objects.filter(membresia__condominio=c).count(),
                "suscripciones": SuscripcionRecurrente.objects.filter(membresia__condominio=c).count(),
            }
            if any(quedan.values()):
                sys.exit(f"Abortado: {c.nombre!r} (id={pk}) todavía tiene datos {quedan} -- no se borra nada.")

        Condominio.objects.filter(pk__in=[PUESTA_DEL_SOL_ID, SOFANOR_PARRA_ID]).delete()
        print(f"-- Condominios id={PUESTA_DEL_SOL_ID} y id={SOFANOR_PARRA_ID} borrados (estaban vacíos).")

    print("\n-- Conteos después:")
    imprimir_conteos(Condominio, Torre, Unidad, Membresia)
    print("\nListo.")


if __name__ == "__main__":
    main()

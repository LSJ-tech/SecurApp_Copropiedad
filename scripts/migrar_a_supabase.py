"""Migra los datos reales de produccion desde el Postgres de Render hacia
Supabase, usando manage.py dumpdata/migrate/loaddata (no hay pg_dump/psql
instalados en esta maquina, y para el tamano de esta base -- 4 condominios
reales -- este metodo sobra).

No es zero-downtime: cualquier escritura en la base de Render entre el
dumpdata y el corte real (cambiar DATABASE_URL en Render, paso aparte,
manual) no viaja a Supabase. Hacerlo en un horario de poco trafico y
cortar apenas termine de correr.

Requiere C:\\Python\\SecurApp_Copropiedad\\.env.migracion (gitignored) con:
    DATABASE_URL_ORIGEN=postgres://...   # Render, External Database URL
    DATABASE_URL_DESTINO=postgres://...  # Supabase, Session pooler URI

Uso: venv/Scripts/python.exe scripts/migrar_a_supabase.py
"""
import datetime
import os
import pathlib
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ENV_MIGRACION = RAIZ / ".env.migracion"
PYTHON = RAIZ / "venv" / "Scripts" / "python.exe"

# Estado efimero / regenerable -- no se copia con PK fija. auth.permission
# va aca tambien (no solo contenttypes): post_migrate la repuebla sola en
# DESTINO y sus IDs de content_type casi seguro no calzan con los de
# ORIGEN -- cargar la version vieja rompe el FK. Esta app no usa grupos/
# permisos de Django para nada (el control de acceso es is_staff +
# Membresia.rol), asi que no hay nada real que perder acá.
APPS_EXCLUIDAS = [
    "contenttypes",
    "auth.permission",
    "admin.logentry",
    "sessions.session",
    "token_blacklist.outstandingtoken",
    "token_blacklist.blacklistedtoken",
]

MODELOS_A_VERIFICAR = [
    "auth.User",
    "core.Condominio",
    "core.Membresia",
    "alertas.Alerta",
    "comunicacion.Aviso",
    "pagos.SuscripcionRecurrente",
    "pagos.Pago",
]


def leer_env_migracion():
    if not ENV_MIGRACION.exists():
        sys.exit(
            f"Falta {ENV_MIGRACION.name} en la raiz del proyecto. "
            "Ver Paso 0 del plan (crear el proyecto en Supabase y sacar "
            "las dos connection strings)."
        )
    valores = {}
    for linea in ENV_MIGRACION.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        valores[clave.strip()] = valor.strip()
    faltantes = [k for k in ("DATABASE_URL_ORIGEN", "DATABASE_URL_DESTINO") if k not in valores]
    if faltantes:
        sys.exit(f"Faltan claves en {ENV_MIGRACION.name}: {', '.join(faltantes)}")
    return valores["DATABASE_URL_ORIGEN"], valores["DATABASE_URL_DESTINO"]


def correr(args, database_url, descripcion):
    print(f"-- {descripcion}")
    env = {**os.environ, "DATABASE_URL": database_url}
    resultado = subprocess.run(
        [str(PYTHON), "manage.py", *args], cwd=RAIZ, env=env, capture_output=True, text=True,
    )
    salida = (resultado.stdout or "") + (resultado.stderr or "")
    # Nunca imprimir el DATABASE_URL (lleva contraseña) aunque aparezca en
    # algun traceback -- se filtra de lo que se muestra en pantalla.
    for secreto in (database_url,):
        salida = salida.replace(secreto, "***")
    print(salida)
    if resultado.returncode != 0:
        sys.exit(f"Fallo: {descripcion} (código {resultado.returncode})")
    return resultado.stdout


def contar_modelos(database_url, etiqueta):
    script = (
        "import django, os; django.setup()\n"
        "from django.apps import apps\n"
        "for ruta in " + repr(MODELOS_A_VERIFICAR) + ":\n"
        "    Modelo = apps.get_model(ruta)\n"
        "    print(f'{ruta}: {Modelo.objects.count()}')\n"
    )
    print(f"-- Conteo de filas ({etiqueta})")
    env = {**os.environ, "DATABASE_URL": database_url, "DJANGO_SETTINGS_MODULE": "config.settings"}
    resultado = subprocess.run(
        [str(PYTHON), "-c", script], cwd=RAIZ, env=env, capture_output=True, text=True,
    )
    print(resultado.stdout or resultado.stderr)
    return resultado.stdout


def main():
    origen, destino = leer_env_migracion()

    backup = RAIZ / f"backup_migracion_{datetime.date.today():%Y%m%d}.json"

    exclude_args = []
    for app in APPS_EXCLUIDAS:
        exclude_args += ["--exclude", app]

    print("Conteos en ORIGEN antes de empezar:")
    contar_modelos(origen, "origen")

    correr(
        ["dumpdata", *exclude_args, "--indent", "2", "--output", str(backup)],
        origen,
        f"dumpdata desde ORIGEN -> {backup.name}",
    )

    correr(["migrate"], destino, "migrate (schema limpio) en DESTINO")
    correr(["loaddata", str(backup)], destino, f"loaddata {backup.name} en DESTINO")

    print("Conteos en DESTINO después de cargar:")
    contar_modelos(destino, "destino")

    print(
        "\nListo. Compara los dos bloques de conteos de arriba -- deben "
        "coincidir modelo por modelo. Si coinciden, seguí con el Paso 3 "
        "del plan (cortar producción). El backup queda en "
        f"{backup} (gitignored, no se commitea)."
    )


if __name__ == "__main__":
    main()

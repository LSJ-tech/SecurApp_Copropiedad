#!/usr/bin/env bash
# Script de build para Render. Se ejecuta en cada deploy.
set -o errexit

# http-ece (dependencia de pywebpush, para Web Push) solo publica .tar.gz en
# PyPI, nunca un wheel -- se excluye de --only-binary o el build falla. Es
# puro Python (sin extensiones en C), así que compilarla no necesita nada
# más que pip/setuptools, no hace falta un compilador de C.
pip install --only-binary :all: --no-binary http-ece -r requirements.txt

python manage.py collectstatic --noinput
python manage.py migrate

# AFP/tramos de impuesto único/periodo semilla para liquidaciones de sueldo.
# Idempotente (update_or_create / get_or_create), seguro de correr en cada
# deploy -- así queda cargado en producción sin pasar por Render Shell.
python manage.py cargar_parametros_previsionales

# Crea el superusuario (dueño de la plataforma) si no existe. No hace nada si
# DJANGO_SUPERUSER_USERNAME/PASSWORD no están definidas (por ejemplo, en local).
python manage.py shell -c "
import os
from django.contrib.auth.models import User

username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')

if username and password and not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f'Superusuario {username!r} creado.')
"

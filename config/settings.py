"""
Django settings for config project (SecurApp Copropiedad).
"""

import datetime
import os
import sys
from pathlib import Path

import dj_database_url
from django.contrib import messages
from django.core.management.utils import get_random_secret_key
from django.urls import reverse_lazy

BASE_DIR = Path(__file__).resolve().parent.parent

# Lo que cambia entre desarrollo y producción se lee de variables de entorno,
# con valores por defecto que mantienen el runserver local funcionando sin
# configurar nada -- mismo patrón que peluqueria_mascota/peluqueria/settings.py.

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY') or get_random_secret_key()

DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = [h.strip() for h in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',') if h.strip()]
if 'test' in sys.argv:
    ALLOWED_HOSTS.append('testserver')

CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()
]


# Application definition

INSTALLED_APPS = [
    # 'core' antes que 'unfold' para que su propio admin (si se agrega) gane
    # sobre el de Unfold. 'unfold' sigue antes que 'django.contrib.admin' --
    # lo exige el propio paquete.
    'core',
    'unfold',
    'unfold.contrib.filters',
    'anymail',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'drf_spectacular',

    'alertas',
    'comunicacion',
    'accesos',
    'gastoscomunes',
    'notificaciones',
    'pagos',
    'personal',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.marca',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# Sin DATABASE_URL (desarrollo), se usa SQLite. En producción, Render provee
# DATABASE_URL automáticamente al conectar un servicio de Postgres.

DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}


AUTHENTICATION_BACKENDS = [
    'core.backends.UsuarioOCorreoBackend',  # permite iniciar sesión con username o email
    'django.contrib.auth.backends.ModelBackend',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_TZ = True


# Static files -- WhiteNoise sirve los estáticos directamente desde la app en
# producción, sin necesitar un servidor web o CDN aparte.

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        # El hash en el nombre de archivo (para cache-busting) solo hace falta
        # en producción -- en local exige correr collectstatic cada vez que
        # se agrega un static nuevo, si no {% static %} tira ValueError.
        'BACKEND': (
            'whitenoise.storage.CompressedManifestStaticFilesStorage' if not DEBUG
            else 'django.contrib.staticfiles.storage.StaticFilesStorage'
        ),
    },
}

PLATFORM_NAME = os.environ.get('PLATFORM_NAME', 'SecurApp Copropiedad')

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'inicio'
LOGOUT_REDIRECT_URL = 'inicio'

MESSAGE_TAGS = {
    messages.ERROR: 'danger',
}


# Email -- se manda por la API HTTP de Resend (vía django-anymail), no por SMTP:
# Render bloquea el tráfico saliente a los puertos SMTP (25/465/587) en
# servicios del plan free -- la conexión se queda colgada contra el firewall
# hasta hacer timeout, lo que puede tirar abajo el worker de gunicorn a mitad
# de una petición (mismo problema ya resuelto así en Clínica Dental El Mirador).
# Sin RESEND_API_KEY (desarrollo), los correos se imprimen en la consola.

if os.environ.get('RESEND_API_KEY'):
    EMAIL_BACKEND = 'anymail.backends.resend.EmailBackend'
    ANYMAIL = {'RESEND_API_KEY': os.environ['RESEND_API_KEY']}
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'no-reply@securapp.local')


# Donación voluntaria vía Mercado Pago (Checkout Pro) de un condominio a
# DevQuad, además de la suscripción mensual ($19.990, ver README) -- no
# extiende ni cambia el plan interno de Condominio (legado, ver core/models.py).
# Distinto del pago de gastos comunes, ver gastoscomunes/models.py.
MERCADOPAGO_ACCESS_TOKEN = os.environ.get('MERCADOPAGO_ACCESS_TOKEN', '')


# Web Push para la PWA (botón de pánico, avisos) -- par de llaves VAPID,
# generadas una sola vez con `manage.py generar_vapid_keys`. Sin configurar,
# el botón de pánico sigue funcionando pero nadie recibe notificación si no
# tiene la app abierta (ver notificaciones/services.py).
VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '')
VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '')
VAPID_CLAIMS_EMAIL = os.environ.get('VAPID_CLAIMS_EMAIL', 'contacto@devquad.cl')


# Django REST Framework + JWT (djangorestframework-simplejwt) -- autenticación
# de la app móvil. Access corto + refresh largo revocable (blacklist), más
# apropiado para sesiones móviles persistentes que un token simple sin expirar.

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        # SessionAuthentication además del JWT: permite que el panel web
        # (logueado con sesión de Django) consuma los mismos endpoints de la
        # API para el polling de alertas, sin duplicar vistas.
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': datetime.timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': datetime.timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'SecurApp Copropiedad API',
    'DESCRIPTION': 'API para la app móvil de residentes (alertas, avisos, gastos comunes, dispositivos push).',
    'VERSION': '1.0.0',
}


# Seguridad en producción (Render termina TLS en su proxy y reenvía por HTTP interno).

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 7
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}


# Tema del admin (django-unfold).

def _logo_admin(request):
    """SITE_LOGO necesita la URL YA resuelta por el storage de static files
    (en producción con hash de cache-busting, ver STORAGES) -- no se puede
    llamar static() al cargar settings.py (la app de staticfiles todavía no
    está lista en ese momento), así que se resuelve acá, perezoso, recién
    cuando Unfold arma el contexto de cada página del admin."""
    from django.templatetags.static import static
    return static("core/logo.svg")


UNFOLD = {
    "SITE_TITLE": "SecurApp Copropiedad · Admin",
    "SITE_HEADER": "SecurApp Copropiedad",
    "SITE_SYMBOL": "shield",
    "SITE_LOGO": _logo_admin,
    "SHOW_HISTORY": True,
    "COLORS": {
        "primary": {
            "50": "238 242 245",
            "100": "220 228 234",
            "200": "185 201 214",
            "300": "143 167 187",
            "400": "92 122 149",
            "500": "60 90 116",
            "600": "26 46 64",
            "700": "20 37 52",
            "800": "15 29 41",
            "900": "10 20 28",
            "950": "5 10 14",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "items": [
                    {"title": "Dashboard", "icon": "dashboard", "link": reverse_lazy("admin:index")},
                ],
            },
            {
                "title": "Condominios",
                "separator": True,
                "items": [
                    {"title": "Condominios", "icon": "apartment", "link": reverse_lazy("admin:core_condominio_changelist")},
                    {"title": "Blocks", "icon": "domain", "link": reverse_lazy("admin:core_torre_changelist")},
                    {"title": "Departamentos", "icon": "door_front", "link": reverse_lazy("admin:core_unidad_changelist")},
                    {"title": "Membresías", "icon": "groups", "link": reverse_lazy("admin:core_membresia_changelist")},
                    {"title": "Códigos de invitación", "icon": "vpn_key", "link": reverse_lazy("admin:core_codigoinvitacion_changelist")},
                    {"title": "Solicitudes de acceso", "icon": "mail", "link": reverse_lazy("admin:core_solicitudacceso_changelist")},
                    {"title": "Solicitudes de eliminación", "icon": "person_remove", "link": reverse_lazy("admin:core_solicitudeliminacion_changelist")},
                ],
            },
            {
                "title": "Operación",
                "separator": True,
                "items": [
                    {"title": "Alertas", "icon": "emergency", "link": reverse_lazy("admin:alertas_alerta_changelist")},
                    {"title": "Avisos", "icon": "campaign", "link": reverse_lazy("admin:comunicacion_aviso_changelist")},
                    {"title": "Accesos", "icon": "meeting_room", "link": reverse_lazy("admin:accesos_registroingreso_changelist")},
                    {"title": "Gastos comunes", "icon": "payments", "link": reverse_lazy("admin:gastoscomunes_gastocomun_changelist")},
                    {"title": "Dispositivos push", "icon": "notifications", "link": reverse_lazy("admin:notificaciones_dispositivopush_changelist")},
                    {"title": "Pagos", "icon": "credit_card", "link": reverse_lazy("admin:pagos_pago_changelist")},
                ],
            },
            {
                "title": "Personal",
                "separator": True,
                "items": [
                    {"title": "Empleados", "icon": "badge", "link": reverse_lazy("admin:personal_empleado_changelist")},
                    {"title": "Liquidaciones", "icon": "receipt_long", "link": reverse_lazy("admin:personal_liquidacion_changelist")},
                    {"title": "AFPs", "icon": "account_balance", "link": reverse_lazy("admin:personal_afp_changelist")},
                    {"title": "Tramos impuesto único", "icon": "calculate", "link": reverse_lazy("admin:personal_tramoimpuestounico_changelist")},
                    {"title": "Parámetros del periodo", "icon": "tune", "link": reverse_lazy("admin:personal_parametrosperiodo_changelist")},
                ],
            },
            {
                "title": "Cuentas",
                "separator": True,
                "items": [
                    {"title": "Usuarios", "icon": "person", "link": reverse_lazy("admin:auth_user_changelist")},
                    {"title": "Grupos", "icon": "shield_person", "link": reverse_lazy("admin:auth_group_changelist")},
                ],
            },
        ],
    },
}

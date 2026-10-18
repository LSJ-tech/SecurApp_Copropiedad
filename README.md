# Mi Barrio+

*(ex SecurApp Copropiedad)*

Red de seguridad y comunicación para juntas de vecinos, condominios, pasajes y barrios en Chile — segundo producto de [DevQuad](https://devquad.cl), en la misma línea que [PataAgenda](https://patagenda.devquad.cl).

Botón de pánico con notificación push, avisos y directorio de vecinos, con un panel web (instalable como PWA). DevQuad administra la configuración de cada condominio (torres, unidades, altas de cuentas) desde un panel propio con acceso a todos los condominios clientes -- no hay un rol de pago operado por el propio condominio. Una app nativa (React Native + Expo) es el siguiente paso si el volumen de clientes lo justifica.

**Mi Barrio+ es gratis.** No hay suscripción ni cobro al condominio -- cualquier residente puede, de forma opcional, activar una donación mensual voluntaria (residente → DevQuad) vía Mercado Pago, cancelable cuando quiera.

## Estado actual

Implementado y probado de punta a punta:

- Multi-tenant real: cada condominio solo ve sus propios datos (verificado con tests de aislamiento).
- 3 roles: **devquad** (`User.is_staff`, sin Membresia propia -- administra TODOS los condominios desde un panel con selector, ver `DevquadCondominiosView`/`condominio_activo_devquad`: miembros, unidades, avisos, Mi condominio, números de emergencia), **delegado** (representa a su propia torre/calle: publica avisos acotados a esa torre, ve el directorio), **residente** (dispara alertas, lee avisos, dona).
- Botón de pánico: la app/API crea una `Alerta` con ubicación GPS, se envía push a todo el condominio (vía Expo), y **cualquier miembro** puede ver el mapa y resolverla o marcarla como falsa alarma. Se auto-cierra sola si nadie responde en 30 minutos. Historial completo filtrable en `/alertas/historial/`.
- Avisos (muro de noticias simple): devquad publica a todo el condominio; un delegado también publica, pero acotado a su propia torre (ver `Aviso.torre`). Se manda push a los destinatarios, todos los miembros leen.
- Panel de devquad con KPIs (unidades, miembros, alertas activas) y accesos directos a Miembros/Torres/Unidades/Mi condominio, con un selector para elegir en qué condominio operar (`/devquad/condominios/`).
- Donación voluntaria (residente → DevQuad, exclusiva de residente/delegado) vía Mercado Pago (API Preapproval -- `SuscripcionRecurrente`), cancelable en cualquier momento desde el panel o el admin. Mismo patrón de seguridad que PataAgenda: el webhook siempre re-consulta el recurso por ID, nunca confía en el body.
- Política de Privacidad y Términos de Uso (`/privacidad/`, `/terminos/`), con aceptación obligatoria al registrarse, y solicitud de eliminación de cuenta/datos desde "Mi perfil".
- Panel de administración (django-unfold) para el dueño de la plataforma.
- API REST documentada con Swagger en `/api/docs/` (drf-spectacular).
- PWA instalable (manifest + service worker en `/sw.js`, íconos propios): ícono en el escritorio del celular, ventana standalone, página de respaldo sin conexión en `/offline/`. **Con Web Push real**: botón de pánico y avisos llegan como notificación del sistema aunque la PWA esté cerrada (VAPID + `pywebpush`, generar el par de llaves con `manage.py generar_vapid_keys`) -- separado de `DispositivoPush`/Expo, que sigue siendo solo para la futura app nativa.
- Compartir una alerta activa por WhatsApp (link `wa.me`, mensaje armado con condominio/torre/unidad/autor), además de la notificación push normal.
- Etiquetas de "Torre" y "Unidad" configurables por condominio (ej. "Block"/"Departamento" para Empart) -- las fija devquad vía `/admin/core/condominio/`, no hay form en la app para esto.
- Correo de bienvenida en HTML al registrarse (autoregistro o alta por devquad), con el mismo look del panel.

No implementado a propósito todavía: QR de visitas, confirmaciones de alerta entre vecinos, reportes, app nativa. **Retirado (ver memoria del proyecto):** gastos comunes, registro de accesos, gestión de personal/liquidaciones de sueldo y la suscripción de pago del condominio -- las apps `gastoscomunes`/`accesos`/`personal` se borraron del código; sus tablas quedaron intactas (huérfanas, no gestionadas) en la base de datos de producción. **También retirada: la red vecinal geográfica** (app `vecindario`, registro público por GPS sin condominio) -- se volvió al modelo de alertas cerradas, exclusivas de quien tiene Membresia en un condominio.

## Stack

Django 6 + Django REST Framework + JWT (`djangorestframework-simplejwt`) + PostgreSQL (SQLite en desarrollo) + Bootstrap (panel web) + django-unfold (admin) + Mercado Pago (donaciones) + Expo/Web Push (notificaciones) + reportlab (PDFs: boucher y liquidación de sueldo) + mindicador.cl (UTM/UF en vivo para liquidaciones).

## Desarrollo local

```bash
python -m venv venv
source venv/Scripts/activate   # Windows (git bash)
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Panel web: `http://127.0.0.1:8000/`. Documentación de la API: `http://127.0.0.1:8000/api/docs/`.

Tests: `python manage.py test` (cubre permisos por rol, el gate de Términos/Privacidad, y donaciones/webhook de Mercado Pago).

## Estructura

```
config/            # settings.py, urls.py (equivalente a "peluqueria/" en PataAgenda)
core/               # Condominio, Torre, Unidad, Membresia, auth JWT, mixins de tenant, panel de devquad
alertas/            # botón de pánico
comunicacion/       # avisos
notificaciones/     # dispositivos push y envío vía Expo/Web Push
pagos/              # donaciones voluntarias (Mercado Pago)
```

Cada app de dominio (excepto `core`) sigue el mismo patrón: `models.py`, `serializers.py` + `api_views.py` + `api_urls.py` (API para la app móvil, bajo `/api/v1/`), y `views.py`/`forms.py`/`urls.py` cuando además tiene panel web.

## Despliegue

Mismo patrón que PataAgenda: `build.sh` + `render.yaml` para Render (Blueprint con web service + Postgres). Variables de entorno en `.env.example`.

## Roles

- **devquad** (`User.is_staff`, no es un valor de `Membresia.rol`): miembros, torres, unidades, avisos, números de emergencia, Mi condominio -- de TODOS los condominios, eligiendo en cuál operar desde `/devquad/condominios/`. Como `Membresia.user` es `OneToOneField`, una cuenta no puede tener membresías en varios condominios a la vez -- devquad no necesita una, opera vía el condominio activo en la sesión (ver `condominio_activo_devquad` en `core/mixins.py`).
- **delegado**: representa su propia torre/calle -- publica avisos acotados a esa torre, ve el directorio de vecinos, dispara/resuelve alertas, dona.
- **residente**: dispara alertas, lee avisos, dona. **No** ve el directorio de vecinos (decisión de producto).

Cualquier rol puede ver y resolver alertas de pánico. Solo residente/delegado pueden donar. Las cuentas de residente y delegado las crea devquad desde `/miembros/nuevo/` (contraseña temporal generada automáticamente, se muestra una sola vez) -- el formulario nunca ofrece crear otra cuenta devquad, esa se da de alta fuera del panel (Django admin, `is_staff=True`).

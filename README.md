# SecurApp Copropiedad

SaaS de emergencias y gestión para juntas de vecinos y condominios en Chile — segundo producto de [DevQuad](https://devquad.cl), en la misma línea que [PataAgenda](https://patagenda.devquad.cl).

Botón de pánico con notificación push, comunicación vecinal (avisos), gestión de accesos, gastos comunes y gestión de personal (empleados + liquidaciones de sueldo reales), con un panel web (instalable como PWA) para directiva/administración/conserjería/residentes. Una app nativa (React Native + Expo) es el siguiente paso si el volumen de clientes lo justifica.

**SecurApp Copropiedad es gratis para lo esencial** (botón de pánico, avisos, accesos). El sistema de gestión de administración -- generar gastos comunes y gestionar personal/liquidaciones de sueldo -- **cuesta $19.990 al mes, fijo**, sin importar cantidad de unidades ni de residentes, lo paga administración, e incluye soporte continuo. Si la suscripción no está al día, los residentes nunca pierden acceso a lo ya generado (sus cuotas, sus comprobantes) -- solo se pausa generar cosas nuevas (`SuscripcionActivaMixin`, ver `core/mixins.py`). Todo condominio nuevo parte con **20 días de prueba gratis** (default de `Condominio.pagado_hasta`, ver `core/models.py`). El pago es un cobro automático mensual con Mercado Pago (`SuscripcionPagarView`, API Preapproval -- se autoriza una vez y Mercado Pago cobra solo cada mes hasta que directiva/administración lo cancele). Además, cualquier residente puede activar una donación mensual automática (residente → DevQuad) por el mismo medio, también cancelable cuando quiera.

## Estado actual

Implementado y probado de punta a punta:

- Registro self-service de un condominio (crea Condominio + cuenta de directiva). Las torres las configura DevQuad al dar de alta al cliente; las unidades las carga la directiva/administración.
- Multi-tenant real: cada condominio solo ve sus propios datos (verificado con tests de aislamiento).
- 5 roles: **directiva** (gobierno: miembros, unidades, avisos, accesos, Mi condominio), **administración** (día a día, incluyendo lo exclusivo de gastos comunes -- generar el cargo del periodo y los datos de transferencia, que ni la directiva puede tocar), **conserjería** (accesos), **delegado** (representa a su propia torre/calle: publica avisos acotados a esa torre), **residente**.
- Botón de pánico: la app/API crea una `Alerta` con ubicación GPS, se envía push a todo el condominio (vía Expo), y **cualquier miembro** (no solo directiva/conserjería) puede ver el mapa y resolverla o marcarla como falsa alarma. Se auto-cierra sola si nadie responde en 30 minutos. Historial completo filtrable en `/alertas/historial/`.
- **Red vecinal geográfica (app `vecindario`, piloto Región de Valparaíso):** capa de emergencia abierta, sin condominio -- cualquier persona en Valparaíso, Viña del Mar o Casablanca se registra con su dirección/GPS (`/vecindario/registro/`) y queda agrupada por "barrio" (celda de geohash + sus 8 vecinas, ~5km) para notificación por radio geográfico, no por tenant. Quien no tiene condominio usa `/mi-barrio/` como dashboard; quien tiene ambos (condominio + red vecinal) ve un toggle opcional "avisar también a mi barrio" en el botón de pánico normal, apagado por defecto. Geocodificación vía Nominatim/OpenStreetMap (gratis, sin API key). Los vecinos de condominios ya existentes se suman solos vía el management command `backfill_perfiles_geograficos` (dry-run por defecto, `--aplicar` para ejecutar).
- Avisos (muro de noticias simple): directiva/administración publican a todo el condominio; un delegado también publica, pero acotado a su propia torre (ver `Aviso.torre`). Se manda push a los destinatarios, todos los miembros leen.
- Accesos: registro manual de ingresos por conserjería/directiva/administración desde el panel (sin QR todavía).
- Gastos comunes: **administración** (exclusivo, ni directiva, y solo con la suscripción al día) genera el cargo del periodo (se prorratea automático por alícuota, cuota fija por unidad, o en partes iguales) y define los datos de transferencia; directiva/administración marcan cuotas como pagadas a mano; cada residente solo lee las suyas (sin pago online todavía), y nunca pierde acceso a lo ya generado aunque la suscripción venza.
- Panel de directiva/administración con KPIs (unidades, miembros, alertas activas, morosidad) y accesos directos a las secciones principales.
- Cobro automático recurrente de la suscripción (`SuscripcionPagarView`, exclusivo directiva/administración, monto fijo) y donación voluntaria (exclusiva residente), ambos vía Mercado Pago (API Preapproval -- `SuscripcionRecurrente`), cancelables en cualquier momento desde el panel o el admin. Mismo patrón de seguridad que PataAgenda: el webhook siempre re-consulta el recurso por ID, nunca confía en el body. Cada cobro mensual aprobado crea un `Pago` nuevo; solo si es de tipo "suscripcion" extiende `Condominio.pagado_hasta` 30 días -- una donación nunca lo toca. No se puede activar una segunda suscripción/donación automática si ya hay una activa.
- Política de Privacidad y Términos de Uso (`/privacidad/`, `/terminos/`), con aceptación obligatoria al registrarse (o en el primer login para cuentas creadas por la directiva), y solicitud de eliminación de cuenta/datos desde "Mi perfil".
- Panel de administración (django-unfold) para el dueño de la plataforma.
- API REST documentada con Swagger en `/api/docs/` (drf-spectacular).
- PWA instalable (manifest + service worker en `/sw.js`, íconos propios): ícono en el escritorio del celular, ventana standalone, página de respaldo sin conexión en `/offline/`. **Con Web Push real**: botón de pánico y avisos llegan como notificación del sistema aunque la PWA esté cerrada (VAPID + `pywebpush`, generar el par de llaves con `manage.py generar_vapid_keys`) -- separado de `DispositivoPush`/Expo, que sigue siendo solo para la futura app nativa.
- Comprobante de pago (boucher) en PDF para cada cuota de gasto común pagada, con firma electrónica simple (sello + código de verificación) -- descargable y enviable por correo a un destinatario elegido por quien marca la cuota como pagada (no se manda solo a todos los residentes de la unidad).
- Compartir una alerta activa por WhatsApp (link `wa.me`, mensaje armado con condominio/torre/unidad/autor), además de la notificación push normal.
- Etiquetas de "Torre" y "Unidad" configurables por condominio (ej. "Block"/"Departamento" para Empart) -- las fija DevQuad vía `/admin/core/condominio/`, no hay form en la app para esto.
- Correo de bienvenida en HTML al registrarse (autoregistro o alta por directiva/administración), con el mismo look del panel.
- **Gestión de personal** (`personal/`, crear empleado/generar liquidación exigen la suscripción al día): empleados del condominio (conserjería, aseo) con datos laborales, y liquidaciones de sueldo reales -- AFP, salud (Fonasa o Isapre en UF), seguro de cesantía según tipo de contrato, impuesto único por tramos (UTM), gratificación legal opcional (configurable por empleado, apagada por defecto). La UTM/UF de cada periodo se consultan solas en `mindicador.cl`; las tasas de AFP y los tramos de impuesto único son tablas globales que DevQuad mantiene a mano cuando cambien (cambian con 90 días de aviso por ley, no es mensual). PDF de la liquidación con el mismo formato de una liquidación real (dos columnas, certificado de recepción con firma), descargable y enviable por correo.

No implementado a propósito todavía: QR de visitas, encuestas, pago online de gastos comunes (residente → administración, eso sigue siendo manual/por transferencia; el pago de la suscripción condominio → DevQuad sí es online), confirmaciones de alerta entre vecinos, reportes, asignación familiar/horas extra en liquidaciones, app nativa.

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

Tests: `python manage.py test` (cubre permisos por rol, el gate de Términos/Privacidad, el gate de suscripción, y pagos/webhook de Mercado Pago).

## Estructura

```
config/            # settings.py, urls.py (equivalente a "peluqueria/" en PataAgenda)
core/               # Condominio, Torre, Unidad, Membresia, auth JWT, mixins de tenant
alertas/            # botón de pánico
comunicacion/       # avisos
accesos/            # registro de ingresos (conserjería)
gastoscomunes/      # cuotas del condominio, comprobante de pago (boucher)
notificaciones/     # dispositivos push y envío vía Expo/Web Push
pagos/              # suscripción online + donaciones voluntarias (Mercado Pago)
personal/           # empleados y liquidaciones de sueldo
```

Cada app de dominio (excepto `core`) sigue el mismo patrón: `models.py`, `serializers.py` + `api_views.py` + `api_urls.py` (API para la app móvil, bajo `/api/v1/`), y `views.py`/`forms.py`/`urls.py` cuando además tiene panel web.

## Despliegue

Mismo patrón que PataAgenda: `build.sh` + `render.yaml` para Render (Blueprint con web service + Postgres). Variables de entorno en `.env.example`.

## Roles

- **directiva**: miembros, unidades, avisos, accesos, más lo exclusivo de gobierno (Mi condominio, link/QR de autoregistro, nombrar otra directiva/administración). **No** incluye generar gastos comunes, editar los datos de transferencia, ni crear/editar empleados o liquidaciones -- eso es exclusivo de administración, a pedido explícito del cliente (es la única área donde administración tiene más permiso que directiva). Directiva sí puede ver la lista de personal y sus liquidaciones, solo no generarlas.
- **administracion**: el día a día del condominio (miembros, unidades, avisos, accesos), más lo exclusivo de gastos comunes (generar el cargo del periodo, datos de transferencia) y de personal (crear/editar empleados, generar liquidaciones de sueldo) -- puede ser un tercero contratado, no necesariamente un vecino elegido.
- **conserje**: registra accesos.
- **residente**: dispara alertas, lee avisos y sus propias cuotas (uso principal: la app móvil).

Cualquier rol puede ver y resolver alertas de pánico. Solo residente puede donar; solo directiva/administración pueden pagar la suscripción. Las cuentas de conserjería y residentes las puede crear tanto directiva como administración desde `/miembros/nuevo/` (contraseña temporal generada automáticamente, se muestra una sola vez); solo directiva puede nombrar otra directiva o administración.

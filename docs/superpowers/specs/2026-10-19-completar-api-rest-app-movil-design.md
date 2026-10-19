# Completar la API REST de Mi Barrio+ (Fase 1 de la app móvil)

## Intención y por qué

Mi Barrio+ (ex SecurApp Copropiedad) hoy es una web Django server-rendered.
El dueño de DevQuad quiere publicar una app nativa (React Native + Expo) en
App Store y Google Play, para que el producto se vea y se sienta más
confiable ante juntas de vecinos y condominios, no porque la PWA actual
(Web Push vía VAPID) esté fallando técnicamente.

La API REST (DRF + SimpleJWT) ya existe, pero hoy solo cubre una parte del
producto: login/perfil, Alertas (botón de pánico + resolver, con push a
Expo y Web Push) y Avisos. Todo lo demás -- pagos/donaciones, directorio de
vecinos, gestión de miembros/torres/unidades, edición de "Mi condominio",
e invitación/registro de nuevos residentes -- solo existe como vistas HTML
server-rendered, sin equivalente en la API.

Se decidió explícitamente completar **toda** la API antes de empezar a
construir la app (no lanzar por fases con la app). Este documento cubre
solo ese trabajo de backend -- la app móvil en sí es un proyecto aparte,
a diseñar después de que esta API esté lista.

## Alcance: para quién es la app que esta API tiene que soportar

La futura app es para **dos públicos**, ambos ya existentes en el modelo
de datos actual:

1. **Vecinos** (residentes/delegados) -- siempre tienen una `Membresia`
   con un `condominio` fijo. Ya es el caso de hoy en la API existente.
2. **DevQuad** (el dueño, `is_staff`, sin `Membresia` propia) -- administra
   cualquier condominio, uno a la vez. Hoy ese "condominio activo" vive en
   la sesión web (`request.session[DEVQUAD_CONDOMINIO_SESSION_KEY]`, ver
   `core/mixins.py: condominio_activo_devquad`). La app móvil autentica
   con JWT, no mantiene cookies de sesión Django, así que este mecanismo
   **no sirve tal cual** para devquad en la app -- ver decisión D-01 abajo.

## Goals

- Exponer vía DRF todo lo que hoy es solo HTML y que la app nueva necesita
  para tener paridad completa con la web, **excepto pagos** (ver
  Non-goals): directorio de vecinos, miembros/torres/unidades (incluyendo
  Mover de condominio), Mi condominio (editar datos + QR + regenerar
  link), e invitación/registro de nuevos residentes.
- Dar a devquad una forma de elegir y mantener su "condominio activo" vía
  API, sin depender de la sesión web.
- Mantener exactamente los mismos permisos y reglas de negocio que ya
  existen en las vistas HTML equivalentes (quién puede ver/crear/editar
  qué) -- esta fase traduce capacidades existentes a otro transporte, no
  inventa ni cambia reglas de negocio.
- Cobertura de tests para cada endpoint nuevo, mismo estándar que el resto
  del proyecto (TDD, suite completa en verde antes de cada commit).

## Non-goals (fuera de esta fase, a propósito)

- **Pagos/donaciones completos** (`DonarView`, `CancelarDonacionRecurrenteView`,
  `MisDonacionesView`, webhook). El usuario dejó pendiente, a propósito,
  decidir si el cobro ocurre abriendo Mercado Pago en el navegador externo
  (lo más seguro frente a las políticas de Apple/Google) o de otra forma.
  No se construye nada de pagos hasta que esa decisión se tome.
- Construir la app móvil en sí (React Native/Expo, pantallas, navegación,
  diseño visual) -- documento aparte, después de esta fase.
- Cambiar o quitar ninguna vista HTML existente -- todo esto es aditivo,
  vive al lado de `core/views.py` y el resto, sin tocarlas.
- Cuentas de Apple Developer / Google Play -- corresponden al proyecto de
  la app, no a este.

## Anti-goals (qué haría esto un fracaso aunque "funcione")

- Que un endpoint nuevo relaje un permiso que hoy existe en la vista HTML
  equivalente (ej. que un residente pueda ver/mover miembros de otro
  condominio por un descuido en el filtro). El aislamiento multi-tenant
  actual (`CondominioQuerysetMixin`, `TieneCondominioActivo`) es la vara:
  cualquier endpoint nuevo se mide contra eso.
- Que agregar estos endpoints rompa algo de la web actual. Se verifica con
  la suite completa de tests en cada paso, igual que siempre en este
  proyecto.

## Constraints

- Django 6.1.2 + DRF + SimpleJWT (`rest_framework_simplejwt`, con
  blacklist de refresh tokens) ya configurado -- se reusa tal cual, sin
  cambiar el esquema de auth.
- Multi-tenant: todo endpoint nuevo debe resolver el condominio igual que
  los existentes, vía `core/permissions.py: condominio_de_la_api` (o su
  reemplazo ampliado, ver D-01), nunca confiando en un id de condominio
  que mande el cliente sin validar pertenencia/permiso.
- Un solo desarrollador (DevQuad) -- las decisiones de diseño abajo
  priorizan reusar patrones ya existentes en el proyecto (mismos
  serializers/permisos/mixins que las apps `alertas`/`comunicacion` ya
  usan) por sobre inventar una convención nueva.
- TDD obligatorio (`superpowers:test-driven-development`): cada endpoint
  nuevo entra con su test en rojo primero, igual que el resto de la
  sesión de hoy.
- Dos bugs ya conocidos en este proyecto, a evitar de nuevo (ver skill
  `securapp-conventions`): (1) si un ViewSet sobreescribe
  `get_permissions()`, comparar contra `self.action`, nunca contra
  `self.request.method` -- ya pasó con `AvisoViewSet.marcar_leido`
  heredando el permiso de `create` por compartir el verbo POST; aplica
  directo a la acción custom `mover` de D-03. (2) Nunca confiar en una FK
  sensible que mande el cliente sin validar pertenencia server-side.

## Decisiones (D-01..D-06)

**D-01 -- Condominio activo de devquad vía API, sin sesión.**
Se agrega un nuevo endpoint `GET /api/v1/devquad/condominios/` (lista, solo
`is_staff`) y `POST /api/v1/devquad/condominios/<id>/entrar/` que, en vez
de guardar el condominio elegido en `request.session` (que la app móvil no
comparte), devuelve un **JWT con el `condominio_id` embebido como claim
custom** (vía un serializer de token propio, extendiendo
`CustomTokenObtainPairView`/`TokenObtainPairSerializer` que ya existe en
`core/api_urls.py`). La app guarda ese token nuevo y lo manda en cada
request siguiente; `condominio_de_la_api` se extiende para, si el usuario
es staff sin Membresia, leer el condominio del claim del token en vez de
la sesión. La sesión web sigue funcionando igual para el panel HTML
(SessionAuthentication no se toca). Costo si es la decisión equivocada:
re-emitir el token en vez de cambiar un valor de sesión es un poco más
pesado, pero evita inventar manejo de cookies en una app que por defecto
no las gestiona.

*Precisión tras el builder check:* `entrar/` reemite un **par
access+refresh completo** (no solo el access) -- `TokenRefreshSerializer`
deriva el access nuevo copiando los claims que ya traía el refresh
recibido (`rest_framework_simplejwt/serializers.py`), así que si solo se
reemitiera el access, el claim `condominio_id` desaparecería solo en el
primer `/auth/refresh/` (a los 30 min), un bug silencioso. El refresh
token viejo (el que se mandó para llamar a `entrar/`) se blacklistea
explícito en el mismo paso, reusando el mecanismo de blacklist que
`auth/logout/` ya usa hoy -- evita dejar dos refresh tokens vivos para la
misma sesión de devquad.

**D-02 -- Directorio de vecinos.**
`GET /api/v1/directorio/` -- solo lectura, mismo campo que ya expone
`DirectorioVecinosView` hoy (nombre, torre/depto de cada miembro del
condominio activo), mismo permiso (`TieneCondominioActivo`).

**D-03 -- Miembros/Torres/Unidades.**
Nuevos `ModelViewSet` (mismo patrón que `AlertaViewSet`/`AvisoViewSet`):
`MembresiaViewSet` (list/create, y una acción custom `mover` que replica
`MoverMiembroView.form_valid` -- re-apunta `condominio`+`unidad` de la
Membresia, nunca toca la Unidad compartida, mismas reglas que ya quedaron
fijadas hoy: no mueve a otros miembros que comparten unidad, no toca
historial ni donación activa), `TorreViewSet` (list/create),
`UnidadViewSet` (list/create). Permiso: solo staff (equivalente a
`SoloStaffMixin`), igual que las vistas HTML de las que vienen.

**D-04 -- Mi condominio.**
`GET/PATCH /api/v1/condominio/` (datos editables: nombre,
etiqueta_organizacion, dirección, comuna, región, datos_transferencia,
etiqueta_torre, etiqueta_unidad, genero_unidad -- los mismos campos que
`CondominioForm` expone hoy), `POST /api/v1/condominio/regenerar-token/`
(equivalente a `RegenerarTokenResidentesView`, solo staff). El QR en sí
(`QRRegistroResidentesView`) no necesita endpoint -- la app genera el QR
localmente a partir del link, igual que podría hacerlo cualquier cliente.

**D-05 -- Invitación y autoregistro.**
`GET /api/v1/invitacion/` (devuelve el link/texto ya armado, equivalente a
`_contexto_invitacion`, para cualquier miembro autenticado). Para el alta
de un residente nuevo (sin cuenta todavía): `GET /api/v1/registro/<token>/`
(público, devuelve datos del condominio + torres/unidades disponibles,
equivalente al `get_context_data` de `RegistroResidenteView`) y
`POST /api/v1/registro/<token>/` (público, crea `User`+`Membresia`, misma
validación que `RegistroResidenteForm` hoy, incluyendo el caso mixto
torre/casa). Sin estos dos, nadie podría crear una cuenta nueva desde la
app -- tendría que pasar primero por la web.

**D-06 -- Serializers y permisos: reusar, no reinventar.**
Cada endpoint nuevo reusa el mismo patrón ya establecido por `alertas` y
`comunicacion`: un `serializers.py` por app con `ModelSerializer`,
permisos de `core/permissions.py`, y rutas registradas en el `api_urls.py`
de cada app (no todo centralizado en `core`).

*Precisión tras el builder check:* `core/permissions.py` ya tiene
`EsDevquad` (misma lógica de `is_staff` que D-03/D-04 necesitan para sus
recursos solo-devquad) -- se reusa tal cual, no se crea una clase nueva
con otro nombre. Crear un `EsStaffDeLaApi` aparte sería duplicar lo mismo
y es justo el tipo de cosa que el Quality Gate de SonarCloud de este
proyecto suele marcar.

**D-07 -- Paginación: no hay "estilo por defecto" que reusar, se decide acá.**
El proyecto no tiene `DEFAULT_PAGINATION_CLASS` ni paginación en ningún
ViewSet existente (confirmado en el builder check) -- ni `alertas` ni
`comunicacion` paginan hoy. Para no arriesgar cambiar la forma de
respuesta de endpoints ya existentes que la PWA ya consume sin paginar
(coherente con el principio de esta fase: todo aditivo, nada que toque lo
que ya funciona), la paginación se agrega **solo** como `pagination_class`
local en `MembresiaViewSet`/`UnidadViewSet` (los dos casos con volumen
real, ej. Empart) -- no se toca `DEFAULT_PAGINATION_CLASS` a nivel de
settings. `TorreViewSet`/`DirectorioVecinos`/etc. quedan sin paginar por
ahora (volumen bajo, igual que hoy).

## Qué queda a criterio de quien lo construya

- Nombres exactos de los campos de cada serializer (mientras cubran lo
  mismo que la vista HTML equivalente).
- Si `MembresiaViewSet`/`TorreViewSet`/`UnidadViewSet` necesitan también
  `update`/`delete` ahora o se agregan después -- las vistas HTML de hoy
  tampoco tienen edición/borrado de Torre/Unidad, así que no hace falta
  inventarlo de más en esta fase (paridad con lo que existe, no más).
- Orden de implementación entre D-02..D-05 (son independientes entre sí;
  D-01 conviene hacerlo primero porque varios de los otros lo asumen
  disponible para devquad).

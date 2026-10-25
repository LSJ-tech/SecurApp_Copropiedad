# Paridad app móvil vs web: números de emergencia, historial de donaciones, cambiar contraseña, eliminar cuenta

## Intención y por qué

Después de probar por primera vez la app móvil Mi Barrio+ en un dispositivo
real (Android e iOS, 2026-10-25), el dueño de DevQuad sintió que "no es casi
lo mismo que la web". Se hizo una auditoría comparando, para el rol
residente/delegado, qué existe en la web (Django server-rendered) y qué
existe hoy en la app móvil (`app_movil/src/app/(vecino)/`). Se encontraron
4 gaps reales, confirmados por el dueño como los que quiere cerrar:

1. **Números de emergencia** -- no existe ninguna pantalla en el móvil.
2. **Historial de donaciones** -- la pantalla "Donar" del móvil solo
   muestra el estado de la donación actual, sin historial ni totales.
3. **Cambiar contraseña** -- no hay forma de hacerlo desde el móvil.
4. **Solicitar eliminación de cuenta** -- no hay forma de hacerlo desde el
   móvil.

Este documento cubre los 4. No es una fase más grande de "mejorar la UX" en
general -- eso quedó acotado a estos 4 puntos concretos, decidido así por
el dueño en la conversación de brainstorming.

## Hallazgo importante que cambia el alcance de uno de los 4 puntos

**El historial de donaciones YA está expuesto por el backend.**
`pagos/api_views.py: MiDonacionApiView.get()` ya devuelve `pagos` (lista de
pagos pasados vía `PagoResumenSerializer`: monto/estado/fecha_creacion),
`total_donado` y `cantidad_aportes` -- el mismo contenido que
`MisDonacionesView` muestra en la web. El cliente móvil
(`app_movil/src/api/donaciones.ts: MiDonacion`) ya tipa esos 3 campos y ya
los recibe. El único problema es que `donar/index.tsx` los ignora por
completo y solo renderiza `donacion_actual`. **El punto 2 es 100% trabajo
de mobile, sin ningún endpoint nuevo.**

Los puntos 1, 3 y 4 sí necesitan trabajo de backend (1) o solo de mobile (3
y 4, ver D-03).

## Goals

- Pantalla nueva "Números de emergencia" en la app móvil: listar los
  números del condominio (incluidos los nacionales, que se sincronizan
  solos igual que en la web) y permitir **proponer** un número nuevo --
  paridad completa con `NumeroEmergenciaListView`/`ProponerNumeroEmergenciaView`
  (`alertas/views.py`).
- La pantalla "Donar" ya existente muestra el historial de pagos pasados +
  total donado + cantidad de aportes, usando datos que la API ya entrega.
- "Mi perfil" en el móvil gana dos accesos: "Cambiar contraseña" y
  "Solicitar eliminación de cuenta", que abren la página web
  correspondiente en el navegador externo del teléfono -- mismo patrón ya
  usado para el cobro de Mercado Pago (`Linking.openURL`), sin construir
  formularios nativos para esto.
- En el móvil, cada número de emergencia de la lista es tocable y abre el
  marcador nativo del teléfono (`tel:`) -- la web solo muestra el teléfono
  como texto porque no tiene esa capacidad; el móvil sí, y es la razón
  principal por la que esta pantalla importa de verdad en una emergencia.

## Non-goals (fuera de esta fase, a propósito)

- Las "sugerencias por región" que la web ofrece al crear un número
  (`EMPRESAS_SUGERIDAS_POR_REGION`, ver `NumeroEmergenciaListView`) --
  atajo cosmético para rellenar el formulario más rápido, no una función
  core. Se puede agregar después si se pide.
- Aprobar/rechazar propuestas desde el móvil -- eso es solo de devquad/
  staff (`AprobarPropuestaNumeroEmergenciaView`/`Rechazar...`), un rol que
  la app móvil no atiende hoy fuera de la carpeta `(admin)`; no entra en
  este documento.
- Pantallas nativas para cambiar contraseña o eliminar cuenta -- decidido
  explícitamente con el dueño: se abre el navegador externo, no se
  reconstruye el formulario en React Native.
- Cambiar o quitar nada de lo que ya existe en la web.

## Anti-goals (qué haría esto un fracaso aunque "funcione")

- Que un residente vea o pueda proponer números de emergencia de otro
  condominio (aislamiento multi-tenant) -- la vara es la misma que ya usa
  el resto de la API (`CondominioQuerysetMixin`/`TieneCondominioActivo`).
- Que abrir "cambiar contraseña" o "eliminar cuenta" en el navegador
  externo falle silenciosamente o quede roto. **Se documenta
  explícitamente, no se oculta:** el navegador externo del teléfono no
  comparte la sesión Django (cookies) con la app (JWT) -- es muy probable
  que la persona tenga que iniciar sesión de nuevo ahí, una vez, para
  llegar al formulario. Es aceptable (son acciones poco frecuentes) y a
  propósito no se construye ningún mecanismo de SSO/single-sign-on nuevo
  para evitarlo en esta fase.
- Que un número de teléfono con espacios (ej. "600 600 5000") rompa el
  marcador nativo al tocarlo.

## Constraints

- Mismas convenciones ya establecidas en el proyecto (skill
  `securapp-conventions`): mixins de rol antes de los de condominio,
  `CondominioQuerysetMixin` en cualquier ViewSet nuevo con datos ligados a
  `Condominio`, comparar por `self.action` nunca por `self.request.method`
  en `get_permissions()`, nunca confiar en una FK sensible que mande el
  cliente sin validar pertenencia server-side.
- TDD obligatorio, suite completa en verde antes de cada commit (~450-470
  tests hoy, 90-140s).
- Reusar los mismos patrones que ya usan `alertas`/`pagos` en su API: un
  `serializers.py` por app, permisos de `core/permissions.py`, rutas en el
  `api_urls.py` de cada app (ver D-06 del diseño previo de la API,
  `2026-10-19-completar-api-rest-app-movil-design.md`).
- Nada de Firebase/push nuevo -- no aplica a este trabajo.
- El cliente móvil ya expone `API_BASE_URL` (`app_movil/src/api/client.ts`)
  para armar URLs completas hacia la web (`Linking.openURL`).

## Decisiones (D-01..D-05)

**D-01 -- Endpoints nuevos para números de emergencia (`alertas` app).**
Dos `ModelViewSet` nuevos en `alertas/api_views.py`, registrados en
`alertas/api_urls.py` junto al `AlertaViewSet` ya existente:

- `NumeroEmergenciaViewSet(CondominioQuerysetMixin, viewsets.ReadOnlyModelViewSet)`,
  `http_method_names = ["get"]`. Su `get_queryset()` primero sincroniza
  `NUMEROS_NACIONALES` con `get_or_create` (mismo bloque que
  `NumeroEmergenciaListView.get_queryset`, condominio = el resuelto por
  `condominio_de_la_api`) y después llama a `super().get_queryset()` para
  que `CondominioQuerysetMixin` aplique el filtro por condominio. Serializer
  nuevo `NumeroEmergenciaSerializer` (campos: `id`, `categoria`,
  `categoria_display` vía `get_categoria_display`, `nombre`, `telefono`,
  `es_nacional`). Ruta: `router.register("numeros-emergencia", ...)`.
- `PropuestaNumeroEmergenciaViewSet(CondominioQuerysetMixin, viewsets.ModelViewSet)`,
  `http_method_names = ["get", "post"]`. `get_queryset()` filtra además por
  `autor=self.request.user.membresia` (solo las propuestas propias, igual
  que `mis_propuestas` en el contexto de la vista web -- nunca las de otro
  residente). `perform_create` exige una Membresia real (mismo patrón que
  `AlertaViewSet.perform_create`: sin Membresia, `PermissionDenied`) y fija
  `autor=membresia`, `condominio=membresia.condominio` (nunca aceptar un
  `condominio` que mande el cliente). El modelo ya pone `estado="pendiente"`
  por default. Serializer nuevo `PropuestaNumeroEmergenciaSerializer`
  (campos: `categoria`, `nombre`, `telefono`, `nota`, de solo escritura en
  creación; `estado`, `fecha_creacion` de solo lectura). Ruta:
  `router.register("propuestas-numero-emergencia", ...)`.
  *(Decisión del builder check: `categoria` tiene `default="otro"` en el
  modelo, lo que hace que `ModelSerializer` de DRF la marque como NO
  requerida por defecto -- a diferencia de `PropuestaNumeroEmergenciaForm`
  (Django `ModelForm`), que sí la exige. El serializer nuevo debe declarar
  `categoria` explícitamente como requerida, para igualar el
  comportamiento de la web.)*

Permiso de ambos: `[IsAuthenticated, TieneCondominioActivo]` (cualquier
residente/delegado con condominio activo -- la web tampoco restringe por
rol la lectura ni la propuesta, solo el alta directa y la aprobación, que
no entran en esta fase).

**D-02 -- Historial de donaciones: solo mobile, sin backend.**
`donar/index.tsx` se amplía para mostrar, debajo del bloque de
donación/estado que ya existe, una sección de historial usando
`datos.pagos`/`datos.total_donado`/`datos.cantidad_aportes` (ya vienen en
la respuesta de `obtenerMiDonacion()`, sin tocar `src/api/donaciones.ts`).
Lista simple (fecha, monto, estado de cada pago) + los dos totales arriba.
Si `pagos` viene vacío, mostrar un texto tipo "Todavía no tienes
donaciones registradas" en vez de una lista vacía o un total "$0.00" sin
contexto.

**D-03 -- Cambiar contraseña / Eliminar cuenta: enlaces que abren el navegador externo.**
Dos botones nuevos en `perfil/index.tsx` que llaman
`Linking.openURL(`${API_BASE_URL}/mi-perfil/cambiar-contrasena/`)` y
`Linking.openURL(`${API_BASE_URL}/mi-perfil/eliminar-cuenta/`)`
respectivamente (mismas URLs que ya expone `core/urls.py`, nombres
`cambiar-contrasena`/`solicitar-eliminacion`). Sin backend nuevo. Ver el
anti-goal de arriba sobre el posible re-login en el navegador -- es
esperado, no es un bug a corregir en esta fase.

**D-04 -- Dónde entra "Números de emergencia" en la navegación.**
Pantalla nueva `app_movil/src/app/(vecino)/numeros-emergencia/index.tsx`,
agregada como ítem nuevo del Drawer en `_layout.tsx` (junto a "Alertas").
Muestra la lista de números (D-01) y, debajo, acceso para proponer uno
nuevo. Queda a criterio de quien construya si el formulario de "proponer"
vive en la misma pantalla (sección colapsable) o en una ruta separada
(`numeros-emergencia/proponer.tsx`) -- ambas formas son válidas y ninguna
cambia el comportamiento.

**D-05 -- Tocar un número para llamar.**
Cada número de la lista es un elemento tocable que ejecuta
`Linking.openURL(`tel:${telefono}`)`. El valor de `telefono` se limpia de
espacios antes de armar el link (`telefono.replace(/\s+/g, "")`) -- ver
Review Focus #4, los números reales en `NUMEROS_NACIONALES` y los que
carga cada condominio vienen con espacios (ej. "600 360 7777").

## Review Focus

- Proponer sin `categoria`/`nombre`/`telefono` debe rechazarse igual que
  en la web (mismos campos obligatorios de `PropuestaNumeroEmergenciaForm`)
  -- probar que el serializer/ViewSet nuevo valida esto.
- Un usuario autenticado sin `Membresia` propia (ej. un devquad sin rol de
  residente) que intente `POST /propuestas-numero-emergencia/` debe recibir
  un rechazo claro, no un 500 -- mismo patrón que `AlertaViewSet.perform_create`.
- Lista de pagos de donación vacía (nunca donó) no debe romper la pantalla
  ni mostrar un total confuso -- ver mensaje explícito de D-02.
- Un teléfono con espacios (ej. "600 600 5000") al armar `tel:` -- debe
  limpiarse antes, no pasarse tal cual (D-05).
- Que un residente proponga un número que ya existe como nacional (ej.
  "133") no debe romper nada -- la web tampoco lo bloquea hoy (sin unique
  constraint entre `PropuestaNumeroEmergencia` y `NumeroEmergencia`), así
  que el endpoint nuevo debe comportarse igual (queda duplicado y
  pendiente de revisión humana, no es una regresión a corregir acá).

## Qué queda a criterio de quien lo construya

- Nombres exactos de archivos/componentes nuevos del lado mobile (pantalla
  de "proponer" separada o inline dentro de `numeros-emergencia/index.tsx`).
- Si "mis propuestas" (las propias, pendientes/aprobadas/rechazadas) se
  muestra en la misma pantalla de la lista de números o en una sección
  separada dentro de ella.
- Estilo visual exacto de las pantallas nuevas -- se reusa el theme ya
  existente (`@/theme/colores`), sin inventar uno nuevo.
- Si el número de teléfono se muestra con un ícono junto al texto o solo
  como texto tocable.
- Orden de implementación entre D-01/D-02/D-03 (son independientes entre
  sí).

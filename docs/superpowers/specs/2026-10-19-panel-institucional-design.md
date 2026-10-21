# Panel institucional de emergencias (Fase 3)

## Intención y por qué

Mientras se brainstormeaba la app móvil (Fase 2) surgió una idea mejor
para "cómo se entera alguien sin el celular encima de una alerta": en vez
de forzar notificaciones push en la versión web de la app, construir un
**panel web separado, en tiempo real**, pensado para quedar abierto todo
el día en el monitor de una municipalidad, bomberos, carabineros u otra
institución de respuesta a emergencias -- como una pantalla de despacho.
Es potencialmente más rápido que cualquier notificación individual: el
operador ya está mirando la pantalla cuando la alerta aparece.

Esta fase va **después** de publicar la app de vecinos/devquad (Fase 2),
confirmado con el usuario -- no en paralelo.

## Alcance: para quién

Un público nuevo, distinto a los dos de las fases anteriores: **cuentas
institucionales** (municipalidad, bomberos, carabineros, etc.), cada una
asociada a una comuna. Ven únicamente las alertas de los condominios
ubicados en su comuna (`Condominio.comuna`, campo que ya existe) -- nunca
las de otras comunas.

## Goals

- Panel web (no celular) que un operador deja abierto todo el día,
  mostrando las alertas activas de su comuna en tiempo real.
- Mapa con pines de ubicación + lista tipo bandeja, juntos en la misma
  pantalla (decidido con mockups -- ver Decisiones).
- Suficiente información para que quien responde sepa adónde ir y a quién
  contactar: nombre, apellido, dirección y teléfono de quien mandó la
  alerta -- mientras esté **activa**.
- Compartir las alertas con la institución de la comuna es **automático**
  para todo condominio de Mi Barrio+ (no un interruptor que alguien tenga
  que prender), **divulgado en los términos/política de privacidad** que
  cualquier miembro ya acepta al crear su cuenta.

## Non-goals (fuera de esta fase, a propósito)

- Que el panel permita modificar nada (marcar "atendida", escribir notas,
  etc.) -- v1 es de **solo lectura**: la fuente de verdad del estado de
  una alerta sigue siendo la app/web de Mi Barrio+.
- Autoregistro de instituciones -- las cuentas institucionales las crea
  DevQuad a mano, mismo patrón que ya usa para dar de alta un condominio
  nuevo.
- Cobertura nacional sin acotar por comuna, o elegir manualmente qué
  comunas ve cada institución más allá de la propia -- se deja para si
  algún caso real lo pide (ej. bomberos que cubre varias comunas).

## Anti-goals (qué haría esto un fracaso aunque "funcione")

- Mismo anti-goal central que la app: que la información llegue tarde (acá
  significa que el panel tarde en reflejar una alerta nueva).
- Que se filtre un dato personal (nombre/dirección/teléfono) de una alerta
  ya resuelta -- el límite de tiempo en que esos datos son visibles (ver
  D-03) es el corazón de que esto sea legalmente defendible, no un
  detalle de implementación.

## Constraints

- **Prerrequisito real, fuera de esta fase pero necesario antes:** hoy
  ningún residente tiene un teléfono guardado en el sistema (`telefono`
  solo existe en `SolicitudAcceso`, el formulario de leads -- no en
  `Membresia`/`User`). Antes de que el panel pueda mostrar teléfono, hay
  que agregar ese campo al perfil del residente. *Resuelto tras el
  builder check:* queda asignado a la **Fase 2**, no como una reapertura
  de la Fase 1 (que ya se cerró y desplegó) -- la Fase 2 ya va a tocar
  las pantallas de perfil/registro del lado de la app, así que agregar
  `telefono` ahí (modelo, formularios/serializers de perfil y de
  autoregistro, ambos lados web+app) es una ampliación chica y natural de
  ese trabajo, no un proyecto aparte.
- Compartir datos personales automáticamente con una institución externa
  es la parte más sensible legalmente de todo el proyecto -- antes de
  construir esto, la Política de Privacidad y Términos de Uso (contenido
  legal, no código) tienen que explicitar esta práctica con claridad. Eso
  es trabajo del usuario/su asesoría legal, no de quien programe esta
  fase, pero bloquea el lanzamiento real (no el desarrollo).
- Reusa el campo GPS (`Alerta.latitud`/`longitud`) que la Fase 2 ya decidió
  capturar automáticamente en el botón de pánico (D-01 de ese documento)
  -- sin eso, el mapa no tendría de dónde sacar el pin.
- Multi-tenant: esto es una SEGUNDA excepción deliberada al aislamiento
  estricto del resto de la API (la primera ya existe: `ids_red_alertas`
  entre condominios vecinos). Acá el criterio de corte es `comuna`, no
  `condominio` -- hay que diseñarlo como una excepción explícita y acotada,
  igual que la de `AlertaViewSet`, no aflojar el aislamiento en general.

## Decisiones (D-01..D-06)

**D-01 -- Alcance por comuna.** Una cuenta institucional está asociada a
una comuna. Ve las alertas de todos los condominios de Mi Barrio+ cuya
`Condominio.comuna` coincide -- confirmado con el usuario explícitamente
(se descartó ver todo el país).

**D-02 -- Layout: mapa + lista juntos.** Confirmado con mockups (ver
`.superpowers/brainstorm/` de esta sesión, ya no accesible tras cerrar el
servidor -- la decisión queda acá). Mapa a un lado con pines de las
alertas activas (usa el GPS de D-01 de la Fase 2), lista tipo bandeja al
otro lado con las más nuevas arriba, cada fila abre el detalle completo.

**D-03 -- Datos personales solo mientras la alerta está activa.**
Mientras `estado="activa"`: nombre, apellido, dirección y teléfono,
visibles. Apenas pasa a `resuelta`/`falsa_alarma`, el panel deja de
mostrar esos datos -- queda el registro histórico (condominio, tipo,
fecha, estado) sin información personal. Esto requiere que el teléfono
exista en el perfil del residente (ver Constraints) y que el serializer
del endpoint nuevo oculte esos campos según el estado, no solo según el
rol de quien consulta.

*Precisiones tras el builder check (mi criterio):*
- **Qué es "dirección" acá:** no existe (ni va a existir) un campo único
  de dirección exacta -- `Condominio.direccion` es a propósito aproximada
  ("Sector Los Aromos", no una dirección postal), y `Unidad.calle` solo
  aplica a casas, no a torres/deptos. "Dirección" en este panel es la
  **combinación de lo que ya existe**: `Condominio.direccion` (contexto
  aproximado) + la unidad formateada igual que `Unidad.__str__` ya hace
  hoy (torre+depto, o calle+número para una casa) + el pin GPS de la
  propia alerta (`Alerta.latitud`/`longitud`, D-01 de la Fase 2) para la
  ubicación exacta. No hace falta ningún campo nuevo de "dirección
  precisa".
- **Omitir, no dejar en null.** Una alerta resuelta/falsa_alarma no
  incluye las claves `nombre`/`apellido`/`direccion`/`telefono` en el
  JSON -- no las manda con `null`. Es la diferencia entre "esto no se
  comparte" y "esto se comparte pero está vacío", y dado lo sensible del
  tema (ver Anti-goals), tiene que ser lo primero.
- **Patrón de implementación, a propósito distinto del resto del
  proyecto:** este es el único serializer de todo el sistema donde la
  visibilidad de un campo depende del ESTADO de la instancia, no del rol
  de quien consulta -- `AlertaSerializer` (Fase 1) no tiene este
  problema, así que no sirve de plantilla acá. El patrón correcto es
  sobreescribir `to_representation(self, instance)` y decidir por
  instancia según `instance.estado` -- **no** condicionar en `__init__`
  ni con un `fields` kwarg del constructor, que se evalúa una sola vez al
  armar el serializer y por eso NO funciona para el listado (`many=True`)
  -- ahí un mismo serializer renderiza alertas activas y resueltas
  mezcladas en la misma respuesta, y una condición en `__init__` les
  aplicaría la visibilidad de una sola fila a todas.

**D-04 -- Consentimiento automático, divulgado legalmente.** Ningún
condominio tiene que activar nada -- compartir con la institución de su
comuna es automático para todos, con la base legal siendo la Política de
Privacidad/Términos de Uso (contenido legal a actualizar, fuera del
alcance de quien programe esto).

**D-05 -- Cuentas institucionales: alta manual por DevQuad.** Mismo
patrón que `DevquadCrearCondominioView` -- un nuevo tipo de cuenta (ni
`Membresia` de residente/delegado, ni `is_staff` devquad) asociada a una
comuna, que solo puede leer el panel de su comuna. Queda a criterio de
quien lo planifique el mecanismo exacto (un nuevo modelo
`CuentaInstitucional` con su propio `User` vinculado, o un rol nuevo) --
lo que importa es que NO hereda los permisos de devquad ni de ningún
condominio.

*Precisión tras el builder check (mi criterio) -- autenticación, no
JWT.* El panel es una pantalla pensada para quedar abierta todo el día
sin que nadie la toque (D-02, anti-goals) -- el JWT de 30 minutos que usa
la app móvil (Fase 1, pensado para un celular que se abre y se cierra) no
calza acá: necesitaría lógica de refresh silencioso en el frontend solo
para no quedar con la pantalla "pegada". El panel es una superficie web
SEPARADA de la app Expo (no comparte código ni build), así que no hay
ninguna razón para arrastrarle JWT -- usa **autenticación por sesión de
Django**, igual que el resto del panel HTML de Mi Barrio+, que ya
resuelve "quedarse logueado" sin que nadie escriba nada nuevo.

**D-06 -- Solo lectura, sin interacción.** El panel no tiene ninguna
acción de escritura -- ver/resolver una alerta sigue siendo exclusivo de
la app/web de Mi Barrio+. Mecanismo de actualización en tiempo real
(polling periódico vs. WebSocket/SSE) queda a criterio técnico de quien
planifique -- polling simple (ej. cada 10-15s) es el default razonable
para un v1 de solo lectura, sin la complejidad de infraestructura de un
canal persistente.

## Qué queda a criterio de quien lo construya

- Mecanismo exacto de cuentas institucionales (D-05): modelo nuevo vs.
  rol -- lo único fijo es que no se mezcla con `Membresia` ni con
  `is_staff`.
- Mecanismo de actualización en tiempo real (D-06): polling vs. push del
  propio servidor -- polling es el default sugerido, no obligatorio.
- Qué tan atrás llega el "historial" del panel (¿solo lo resuelto hoy?
  ¿últimas 24h, como ya hace el filtro "recientes" de Alertas en el resto
  del sistema?) -- no se definió un número exacto, usar un criterio
  consistente con el resto del proyecto si hace falta uno.
- Tecnología del panel en sí (framework web, librería de mapas) -- no se
  discutió, es una decisión de implementación pura.

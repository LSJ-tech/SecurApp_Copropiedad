# App móvil de Mi Barrio+ (Fase 2)

## Intención y por qué

Mi Barrio+ (ex SecurApp Copropiedad) ya tiene una web/PWA completa y, desde
la Fase 1, una API REST (DRF + JWT) que cubre todo lo que la app necesita
(login, Alertas, Avisos, Directorio, Mi condominio, Miembros/Torres/
Unidades, invitación/registro). Esta fase construye la **app nativa en sí**
-- el dueño de DevQuad quiere publicarla en App Store y Google Play porque
una app en las tiendas transmite más confianza a una junta de
vecinos/condominio que un link de PWA, no porque la PWA esté fallando
técnicamente.

La app tiene que ser **multiplataforma desde un mismo código**: funcionar
igual como app de celular y como app web (confirmado explícitamente por el
usuario). Por eso el stack es **Expo (React Native) + Expo for Web**
(react-native-web) -- una sola base de código, tres salidas (iOS, Android,
Web), sin mantener dos proyectos separados.

## Alcance: para quién

Dos públicos, igual que en la Fase 1:

1. **Vecinos** (residentes/delegados) -- la app completa, con el botón de
   pánico como pantalla de inicio.
2. **DevQuad** -- un **"modo administrador"** claramente separado dentro de
   la misma app (no mezclado en el menú del vecino), para operar
   cualquier condominio: elegir condominio activo, gestionar miembros/
   torres/unidades, editar "Mi condominio".

## Goals

- Réplica completa de lo que hoy hace la web (no un MVP chico) -- el
  usuario lo pidió explícito ("todo"), aunque el ORDEN de construcción
  dentro de la app puede ir por tandas (ver "Cómo se construye" abajo).
- El botón de pánico es el corazón de la app: tiene que ser rápido,
  imposible de malinterpretar, y confiable incluso con mala señal.
- Multiplataforma real: misma base de código para iOS, Android y Web.
- Publicada en App Store y Google Play (cuentas de desarrollador a crear
  como parte de este proyecto).
- **Agregar `telefono` al perfil del residente** (modelo, formulario/
  serializer de "Mi perfil" y de autoregistro, en API y en la pantalla de
  perfil de la app) -- hoy no existe en ningún lado salvo en el
  formulario de leads (`SolicitudAcceso`). Prerrequisito real de la Fase
  3 (Panel institucional), que ya se decidió que corre después de esta
  fase -- se construye acá porque esta fase ya toca esas pantallas.

## Non-goals (fuera de esta fase, a propósito)

- **Pagos/donaciones dentro de la app.** Sigue pendiente decidir si el
  cobro abre Mercado Pago en el navegador externo (lo más seguro frente a
  las políticas de Apple/Google) u otra forma -- no se construye nada de
  pagos hasta que esa decisión se tome (mismo non-goal que la Fase 1).
- **Foto adjunta en una alerta.** Se evaluó y se descartó para v1: no
  aporta a la velocidad (que es la prioridad #1), agrega complejidad de
  backend (hoy `Alerta` no tiene campo de foto, ni hay registro de "visto
  por" -- ver D-05 y D-06), y una foto durante una emergencia puede
  captar a terceros o, en una emergencia médica, contar como **dato
  sensible** bajo la ley chilena de protección de datos (Ley 21.719,
  vigente desde diciembre de 2026). Queda como posible fase futura.
- **Modo silencioso** (mandar la alerta sin abrir el celular ni hacer
  ruido, para no delatar a quien la manda frente a un intruso). Se evaluó
  y se quiere, pero probablemente necesita código nativo fuera de lo que
  Expo da gratis (un config plugin o módulo nativo para un atajo de
  hardware/widget de pantalla bloqueada) -- se deja para una fase futura,
  después de validar la app base.

## Anti-goals (qué haría esto un fracaso aunque "funcione")

- **Que la notificación llegue tarde.** Es la razón de ser de la app --
  si el push tarda, no cumplió su propósito aunque todo el resto esté
  perfecto.
- **Que la gente no la entienda sin que alguien se la explique.** Una
  junta de vecinos tiene gente de todas las edades y niveles de manejo de
  celular -- el flujo del botón de pánico tiene que ser obvio a primera
  vista, sin curva de aprendizaje.

## Constraints

- Stack: Expo (React Native) + Expo for Web, TypeScript. Build/publish vía
  EAS (Expo Application Services) -- permite compilar para iOS sin
  necesitar una Mac propia.
- Consume la API REST de la Fase 1 tal cual (`api/v1/...`, JWT). No se
  modifica el backend salvo lo explícito en las Decisiones de abajo
  (D-05, D-06 agregan campos/endpoints nuevos y acotados).
- Cuentas de Apple Developer (USD 99/año) y Google Play Console (USD 25
  único) todavía no existen -- crearlas es parte de este proyecto, antes
  de poder publicar (no antes de poder desarrollar/probar).
- Diseño visual propio (sin app de referencia) -- colores/tipografía ya
  definidos en el rebrand "Mi Barrio+" de la web (`core/static/core/
  brand.css`), se reusan como punto de partida para mantener consistencia
  de marca entre web y app.
- Push notifications: ya existe la infraestructura del lado backend
  (`DispositivoPush`, Expo Push API) desde antes de la Fase 1 -- esta fase
  consume eso, no lo reconstruye. **Confirmado con el usuario:** el push
  de esta app queda acotado a celular (iOS/Android) -- la salida Web de
  Expo for Web no integra Web Push/VAPID (eso seguirá siendo exclusivo de
  la PWA actual). Ver también el nuevo "Panel institucional" más abajo,
  que es la respuesta real a "cómo se entera alguien sin el celular
  encima".

## Cómo se construye (fases dentro de la app)

Réplica completa es la meta, pero no todo se construye ni se publica a la
vez -- se arma y se lanza en tandas, con actualizaciones después de
publicada en las tiendas (acordado antes de escribir este documento):

1. **Núcleo**: login, botón de pánico completo (con las 4 mejoras de
   D-01..D-04), recibir notificaciones, ver alertas activas/historial.
2. **Lo demás del vecino**: avisos, directorio, mi perfil, invitar/
   compartir.
3. **Modo administrador** (devquad): elegir condominio, miembros/torres/
   unidades, Mi condominio.
4. **Pendientes**: pagos (cuando se resuelva el enfoque), foto en
   alertas, modo silencioso -- cada uno es una decisión aparte, no
   automática.

Después de esta fase viene la **Fase 3: Panel institucional** (ya
brainstormeada, documento aparte:
`docs/superpowers/specs/2026-10-19-panel-institucional-design.md`) -- un
panel web en tiempo real para que municipalidades y otras instituciones de
respuesta a emergencias vean las alertas de su comuna. Confirmado con el
usuario que va DESPUÉS de esta app, no en paralelo.

## Decisiones (D-01..D-07)

**D-01 -- Pantalla de inicio: un botón de pánico grande, nada más
compitiendo por la atención.** Sin barra de navegación inferior (que le
quitaría protagonismo al botón) -- el resto de la app se accede por un
**menú lateral** (drawer), que se abre desde un ícono/gesto de borde,
nunca compitiendo visualmente con el botón.

**D-02 -- Confirmación por press-and-hold de 2 segundos.** Evita que un
roce accidental dispare una alerta, sin agregar un paso de diálogo
("¿seguro?") que frenaría la velocidad. Al soltar antes de los 2 segundos,
no pasa nada (se cancela solo).

**D-03 -- Tipo de alerta: genérico por defecto, específico opcional.** El
botón grande manda `tipo="otro"` (ya existe en el sistema, título
"🚨 Alerta de emergencia") sin pedir que se elija un tipo primero. Al lado
(no encima) del botón grande hay un control más chico que despliega la
lista completa de tipos (robo, incendio, fuga de gas, persona extraña,
etc.) para quien sí tiene tiempo de precisar. Nunca se bloquea el camino
rápido para forzar a elegir tipo.

**D-04 -- Las 4 mejoras al flujo de envío, confirmadas con el usuario:**

1. **Ubicación automática.** Al mantener apretado el botón, la app pide
   (si no la tiene ya) el permiso de ubicación y captura
   latitud/longitud en el momento de enviar la alerta -- sin ningún paso
   extra visible. `Alerta.latitud`/`Alerta.longitud` ya existen en el
   modelo (Fase 1 no los tocó porque la web no los capturaba
   automáticamente); el POST a `/api/v1/alertas/` ya acepta esos dos
   campos, así que esto es trabajo 100% de la app, no del backend.
2. **Reintento automático si falla el envío** (sin señal, timeout). La
   app guarda la alerta localmente si el POST falla y reintenta en
   segundo plano hasta que salga, mostrando el estado ("Enviando...
   reintentando") en vez de fallar en silencio. *Precisión tras el
   builder check:* esto es "mientras la app sigue viva" (primer/segundo
   plano, cola persistida en storage local, reintento al recuperar
   señal) -- NO una garantía a nivel de SO con la app cerrada o el
   teléfono bloqueado. Lo segundo requeriría background fetch nativo
   (en iOS, con throttling de ~15 min, lejos de "hasta que salga" para
   una emergencia) y el mismo tipo de costo técnico (módulo/config
   plugin nativo) que ya sacó a "modo silencioso" de esta fase -- mismo
   criterio aplicado acá para que la fase no se salga de Expo managed.
3. **Ventana de ~10 segundos para cancelar** después de enviada, con un
   botón visible "Cancelar, fue un error" -- llama al mismo endpoint de
   resolver (`PATCH /api/v1/alertas/<id>/resolver/` con
   `estado=falsa_alarma`) que ya existe. **Confirmado con el usuario:** el
   push a los vecinos sale de inmediato al crear la alerta, SIN esperar
   la ventana de cancelar (no se toca el backend, ninguna alerta real se
   atrasa). "Cancelar" dispara un segundo push de "alerta resuelta/falsa
   alarma" (ya construido en la Fase 1, `notificar_alerta_resuelta`), no
   evita el primer aviso.
4. **Modo silencioso**: evaluado y confirmado como deseado, pero
   declarado Non-goal de esta fase por el costo técnico (ver arriba) --
   fase futura.

**D-05 -- "Visto por" en una alerta (nuevo, backend).** Después de enviar,
la pantalla de confirmación muestra el estado actual de la alerta (ya
existe: activa/resuelta/falsa_alarma) y quién de los vecinos ya la vio --
esto SÍ es trabajo nuevo de backend, mismo patrón que `AvisoLectura` ya
usa para Avisos (un modelo `AlertaLectura` o similar, con su propio
endpoint). Se deja a quien planifique la implementación decidir el diseño
exacto del modelo/endpoint, siguiendo el patrón ya probado de
`AvisoLectura`/`marcar_leido`.

*Precisiones tras el builder check (mi criterio, no cambian el alcance):*
- **Qué cuenta como "visto":** una acción explícita del vecino (igual que
  `marcar_leido` en Avisos -- el cliente la llama a propósito, nunca una
  sincronización pasiva en segundo plano), no el solo hecho de que el
  dispositivo reciba el push. Sincronizar pasivamente daría un conteo que
  miente justo en el peor momento (alguien "vio" la alerta con el
  teléfono en el bolsillo).
- **A quién se cuenta:** solo a miembros del condominio dueño de la
  alerta, no a los condominios vecinos de la red de alertas
  (`ids_red_alertas`) aunque también la reciban -- el "visto por" es
  reaseguro para la propia comunidad, no una métrica de toda la red.
- **Quién lo ve (confirmado con el usuario):** solo el propio autor de la
  alerta, no todo el condominio -- es reaseguro personal ("ya 3 vecinos
  la vieron"), nadie más necesita ese detalle.

**D-06 -- Foto en alertas: explícitamente fuera (ver Non-goals).** No se
agrega campo ni endpoint para esto en esta fase.

**D-07 -- Modo administrador separado, no integrado al menú del vecino.**
Devquad entra a una sección distinta de la app (podría ser una pantalla de
"elegir modo" post-login si la cuenta es staff, o un toggle visible solo
para esa cuenta) que agrupa: elegir condominio activo (ya construido en
Fase 1, D-01 de ese plan), miembros/torres/unidades, Mi condominio. No
comparte navegación con el drawer del vecino.

## Qué queda a criterio de quien lo construya

- Estructura exacta de carpetas/navegación de Expo Router (o React
  Navigation) -- cualquiera de las dos es válida, se elige según lo que
  esté más probado en la versión de Expo que se use al momento de armar
  el plan de implementación.
- Diseño exacto del modelo `AlertaLectura` (D-05): nombres de campos,
  exacto shape del endpoint -- seguir el patrón de `AvisoLectura` como
  referencia, no reinventar la forma.
- Cómo se distingue visualmente "modo administrador" del resto (pantalla
  separada vs. toggle) -- ambas cumplen el requisito de D-07 de no
  mezclarse con el menú del vecino.
- Paleta/tipografía exacta tomada de `core/static/core/brand.css` --
  adaptarla a componentes de React Native (no son CSS directo).
- Orden exacto de construcción dentro de cada tanda de "Cómo se
  construye" -- las 4 tandas son la guía, el orden fino dentro de cada
  una no es crítico.

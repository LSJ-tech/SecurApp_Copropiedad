# Pantalla principal del móvil: mezclar el pánico con el contenido de la web

## Intención y por qué

El usuario probó la app móvil Mi Barrio+ en su propio dispositivo y sintió
que, comparada con la web, "la experiencia no es grata" -- la pantalla
principal del celular (`(vecino)/index.tsx`) es casi vacía: solo el
círculo gigante de pánico, sin nada del contenido que la web sí muestra
(donar, mi departamento, invitar vecinos, alertas activas).

Se armaron 3 mockups (wireframes) comparando dónde vive el botón de
pánico respecto al resto del contenido -- el usuario eligió explícitamente
la opción **C**: el círculo se aplana a una franja roja fija arriba de
toda la pantalla (como ya existe la franja "Alertas activas" en la web),
dejando todo el resto del espacio disponible, con scroll, para el
contenido que hoy solo está en la web.

**Precisión importante encontrada durante la conversación:** la web NO
usa "mantener presionado 2 segundos" -- tiene su propio mecanismo (un
botón flotante que al tocarlo abre un modal para elegir el tipo de
emergencia y confirmar). El usuario confirmó explícitamente que **cada
plataforma mantiene su propio mecanismo para disparar la alerta** -- este
documento NO cambia nada del lado de la web, ni unifica cómo se dispara
la alerta entre plataformas. Lo que se unifica es el diseño/contenido
alrededor.

## Goals

- Rediseñar `app_movil/src/app/(vecino)/index.tsx` para que, debajo de
  una franja de pánico fija y compacta (en vez del círculo gigante
  actual), muestre el mismo contenido que ya existe en
  `core/templates/core/inicio.html` para el rol residente/delegado:
  tarjeta de donación, tarjeta "Mi depto", invitar vecinos (+ directorio
  si es delegado), y alertas activas.
- El mecanismo de pánico (mantener presionado 2s, `BotonPanico.tsx`) se
  mantiene exactamente igual -- solo cambia su estilo visual (de círculo
  centrado a franja fija arriba), no su lógica ni sus props.
- Backend: agregar los campos que hoy le faltan a la API para poder
  mostrar "Mi depto" igual que la web (nombre de la torre, y las
  etiquetas propias de cada condominio -- "Block"/"Departamento" no es
  fijo, cada condominio define las suyas, ver `Condominio.etiqueta_torre`/
  `etiqueta_unidad`/`genero_unidad`).

## Non-goals (fuera de esta fase, a propósito)

- **Estadísticas de Blocks/Departamentos/Vecinos registrados** -- el
  usuario las descartó explícitamente para esta pantalla ("eso es más
  para los delegados y el admin"). No se crea ningún endpoint de conteo
  nuevo.
- Cambiar nada de la web (`core/templates/core/inicio.html` sigue igual).
- Cambiar el mecanismo de pánico de ninguna plataforma, ni unificarlo
  entre ellas -- decisión explícita del usuario.
- El banner de "activa las notificaciones" y el aviso de "cómo instalar
  la app" de la web son específicos de la PWA (Web Push/instalación del
  navegador) -- no aplican a una app nativa, no se traducen al móvil.
- Edición de "Mi depto" desde esta pantalla -- es solo lectura, igual que
  en la web (lo asigna la administración, no el propio residente).

## Anti-goals (qué haría esto un fracaso aunque "funcione")

- Que la franja de pánico deje de ser inmediatamente visible/alcanzable
  al entrar a la pantalla (tiene que seguir fija arriba, nunca dentro del
  área con scroll) -- es la razón de ser de la pantalla.
- Que agregar contenido nuevo rompa el flujo ya probado del botón de
  pánico (envío con GPS, cola de reintento, ventana de cancelar) -- ese
  código no se toca, solo el estilo visual del componente que lo dispara.
- Que un residente de un condominio vea datos (torre, etiquetas) de otro
  condominio -- mismo aislamiento multi-tenant que ya exige el resto de
  la API.

## Constraints

- Mismas convenciones ya establecidas (`securapp-conventions`): TDD
  obligatorio, suite completa en verde antes de cada commit,
  `CondominioQuerysetMixin`/`condominio_de_la_api` para cualquier dato
  nuevo expuesto, nunca confiar en una FK sensible que mande el cliente.
- El mecanismo de pánico (`BotonPanico.tsx`, `SelectorTipoAlerta.tsx`,
  `enviarAlerta.ts`, GPS, cola de reintento, ventana de cancelar) es
  código ya revisado y en producción -- este trabajo solo le cambia el
  estilo visual al contenedor, nunca su lógica interna.
- Reusar lo que ya existe en la API móvil en vez de duplicar: donaciones
  (`src/api/donaciones.ts`), invitación (`src/api/invitacion.ts`, ya
  usada por `(vecino)/invitar/index.tsx`), alertas activas
  (`listarAlertas("activa")` de `src/api/alertas.ts`, ya usado por la
  pestaña de Alertas).

## Decisiones (D-01..D-04)

**D-01 -- Backend: etiquetas del condominio y torre de la unidad.**
`CondominioResumenSerializer` (`core/serializers.py`) gana 3 campos
nuevos: `etiqueta_torre`, `etiqueta_unidad`, `genero_unidad` (ya son
campos del modelo `Condominio`, hoy no expuestos en este serializer).
`UnidadResumenSerializer` gana `torre_nombre` (mismo patrón ya usado en
`MembresiaListSerializer.unidad_torre`:
`serializers.CharField(source="torre.nombre", read_only=True, default=None)`).
Es aditivo -- `CondominioResumenSerializer` también lo usa
`DevquadCondominiosApiView` y el endpoint de "entrar a un condominio" de
devquad, agregar campos no les rompe nada.

**D-02 -- La franja de pánico: mismo componente, otro estilo.**
`BotonPanico.tsx` mantiene exactamente su misma interfaz pública
(props `onConfirmar`/`tipoSeleccionado`; `onPressIn`/`onPressOut` son
manejadores internos sobre el `Pressable`, no props, y tampoco se tocan)
-- solo cambian los estilos de `styles.boton`/
`styles.texto` (de círculo de 220x220 centrado, a una franja roja de
ancho completo, fija en la parte de arriba de la pantalla, con el mismo
texto "Mantén presionado 2 segundos"). `SelectorTipoAlerta` se queda
junto a la franja (mismo lugar relativo que tiene hoy), no se mueve
dentro del contenido con scroll.

**D-03 -- Estructura de `(vecino)/index.tsx`: franja fija arriba, resto con scroll.**
La pantalla pasa a tener dos zonas: una fija arriba (franja de pánico +
selector de tipo + mensaje de error, exactamente lo que ya existe hoy,
solo reubicado) y, debajo, un `ScrollView` con las tarjetas nuevas en
este orden (mismo orden que la web):
1. Tarjeta de donación.
2. Tarjeta "Mi depto".
3. Botón(es) "Invitar vecinos" (+ "Directorio" si el rol es delegado,
   mismo criterio que ya usa el Drawer).
4. Tarjeta de alertas activas.

**D-04 -- Contenido de cada tarjeta nueva: resumen con link, no todo duplicado.**
- *Donación:* tarjeta de solo resumen (estado actual -- "Donación activa
  $2.000/mes" o invitación a donar) con un botón que navega a la
  pantalla `Donar` ya existente (`router.push` al tab `donar`) -- la
  lógica de crear/cancelar la donación NO se duplica acá, vive solo en
  `donar/index.tsx` como hoy.
- *Mi depto:* solo lectura -- `{condominio.etiqueta_torre} {unidad.torre_nombre}, {condominio.etiqueta_unidad en minúscula} {unidad.numero}`
  (mismo armado de texto que `inicio.html`, incluyendo el caso de una
  unidad sin torre asignada -- la web también usa "—" ahí), o "Sin
  {etiqueta_unidad en minúscula} asignad{genero_unidad}" si `unidad` es
  `null`. El dato ya extendido por D-01 sale de `obtenerMiPerfil()`
  (`src/api/auth.ts`) -- pero esta pantalla no necesita llamarlo de
  nuevo: `AuthContext` ya lo trae y lo expone vía `useAuth().membresia`
  al iniciar sesión (mismo patrón que ya usa `avisos/index.tsx` para
  leer `membresia?.rol`), así que alcanza con leerlo del contexto.
- *Invitar vecinos:* reusa lo que ya existe (pantalla/acción de invitar
  de la Tanda 2).
- *Alertas activas:* tarjeta de solo resumen -- llama
  `listarAlertas("activa")` (ya existe), muestra hasta un puñado de
  filas (tipo + hora), cada una navega al detalle
  (`/alertas/[id]`, ya existe); si no hay ninguna, un texto corto tipo
  "Sin alertas activas." (mismo mensaje que ya usa la web).

## Qué queda a criterio de quien lo construya

- Estilo visual exacto de la franja de pánico (alto, tipografía, si el
  selector de tipo queda visible siempre o se revela al tocar "Otro") --
  mientras siga fija arriba y dispare con el mismo mecanismo de 2s.
- Cuántas alertas activas mostrar como máximo en la tarjeta-resumen antes
  de truncar con "Ver todas" (la pestaña de Alertas ya tiene la lista
  completa).
- Nombres exactos de archivos/componentes nuevos (ej. si la tarjeta de
  donación-resumen es un componente separado o JSX inline en
  `index.tsx`).
- Mensaje exacto de la tarjeta "Mi depto" cuando no hay `unidad`
  asignada (seguir el mismo patrón de género que ya usa `inicio.html`).

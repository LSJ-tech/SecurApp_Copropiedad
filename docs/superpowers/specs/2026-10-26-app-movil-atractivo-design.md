# App móvil Mi Barrio+: microinteracciones + estados vacíos ilustrados

## Intención y por qué

Probando el rediseño de color en el emulador, el usuario señaló que la
app en general "se siente plana" más allá del color: no hay ninguna
señal de vida cuando algo pasa (mandar una alerta, por ejemplo, solo
hace aparecer un botón de "Cancelar, fue un error" -- no hay ningún
"listo, se mandó"), y los lugares donde no hay datos todavía muestran
puro texto gris ("Sin alertas activas.") o, en dos pantallas, quedan
directamente en blanco. Se mostraron tres mockups comparables
(microinteracciones solas, estados vacíos ilustrados solos, o ambos) y
el usuario eligió la opción combinada (C).

Este documento cubre esa combinación: una confirmación animada al
mandar una alerta, un saludo personalizado en el home, y estados
vacíos con ícono en vez de texto plano, en las pantallas donde
realmente faltan.

## Qué existe hoy (relevante)

- **Confirmación de alerta**: en `(vecino)/index.tsx`, al mandar una
  alerta con éxito solo aparece `VentanaCancelar` (un botón "Cancelar,
  fue un error" que se autodestruye a los 10s). No hay ningún mensaje
  de éxito -- el residente no tiene ninguna señal de que la alerta
  llegó, más allá de que el botón de pánico dejó de estar presionado.
- **Saludo**: el encabezado del Drawer dice "Mi Barrio+" en todas las
  pantallas (fijo, en `(vecino)/_layout.tsx`). El nombre del residente
  ya está disponible sin pedirlo de nuevo: `membresia.first_name` (o
  `membresia.nombre` completo como respaldo) viene en el mismo
  `useAuth()` que ya usa toda la app.
- **Estados vacíos, por pantalla:**
  - Home (`tarjeta-alertas`) y Alertas→Activas: ya muestran
    `"Sin alertas activas."` en texto plano (la tarjeta en sí ya tiene
    color de fondo correcto del trabajo de sistema visual).
  - Alertas→Historial: sin ningún estado vacío -- un historial vacío
    deja el espacio bajo "Historial" completamente en blanco, mismo
    problema que las dos de abajo.
  - **Avisos** y **Números de emergencia**: sin ningún estado vacío.
    Confirmado probando en el emulador (2026-10-26): con la lista
    vacía, la pantalla entera queda en blanco bajo el encabezado, sin
    ningún texto.

## Objetivos

- Reemplazar el "no hay nada" silencioso por una confirmación visible
  cuando el residente manda una alerta: una tarjeta que aparece con
  una animación breve, un ícono de check, y vibración en el teléfono
  real.
- Reemplazar el "Sin alertas activas." / espacio en blanco por un
  ícono + mensaje en las cinco listas vacías identificadas arriba
  (Home/alertas-activas, Alertas/Activas, Alertas/Historial, Avisos,
  Números de emergencia).
- Agregar un saludo personalizado ("Hola, {nombre} 👋") en el home.

## No-objetivos (fuera de alcance de este documento)

- **Confirmación animada en Donar.** El flujo de donar sale de la app
  (navegador externo de Mercado Pago) y vuelve por `AppState`
  reaccionando a que la app vuelve a quedar activa -- detectar
  confiablemente "se acaba de confirmar, mostrá el toast" ahí implica
  rastrear la transición de estado anterior/nuevo con los tiempos del
  webhook de por medio, lo cual es una pieza bastante más compleja que
  el resto de este documento para un beneficio menor (la confirmación
  de la propia Mercado Pago ya le avisa al residente). El historial de
  pagos vacío ("Todavía no tienes donaciones registradas.") tampoco
  entra -- es la única pantalla de las afectadas que no se señaló como
  problema, y agregarla es trivial más adelante si se pide.
- **Botón de pánico en sí.** No cambia de tamaño, forma, ni
  comportamiento -- debe seguir sintiéndose serio. Las mejoras de este
  documento son en lo que pasa *después* de presionarlo, no en el
  botón mismo.
- **Ilustraciones SVG a medida.** La opción mostrada en los mockups
  usaba un dibujo de escudo hecho a mano; se implementa en cambio con
  `@expo/vector-icons` (Ionicons), que ya es una dependencia del
  proyecto desde el selector de tipo de emergencia -- un ícono más
  grande y centrado logra el mismo efecto visual sin agregar otro
  sistema de assets.

## Anti-objetivos (esto sería un fracaso aunque "funcione")

- Que la confirmación animada haga más lento o menos claro el flujo de
  pánico -- tiene que aparecer *junto* a `VentanaCancelar`, nunca
  bloquear ni demorar el botón "Cancelar, fue un error".
- Que el saludo personalizado rompa si `first_name` viene vacío (dato
  opcional en el tipo `MembresiaOut`) -- tiene que degradar con
  gracia, nunca mostrar "Hola, undefined".
- Que agregar `expo-haptics` rompa la app en el build ya instalado en
  el emulador/dispositivos de prueba (ver Restricciones).

## Restricciones

- `expo-haptics` no está instalado. A diferencia de
  `@expo/vector-icons` (que es JS + fuentes, se recarga solo con
  Metro), es un módulo nativo de verdad -- el dev client ya instalado
  en el emulador y en el iPhone de prueba **no lo tiene enlazado**, así
  que la llamada a `Haptics.notificationAsync(...)` va a fallar en el
  build actual hasta que se genere un build EAS nuevo del dev client.
  La llamada se hace de forma defensiva (nunca puede tirar la
  confirmación visual si la vibración falla), y la verificación real
  de que "se siente" queda pendiente de ese build nuevo -- no es
  verificable hoy mismo en el emulador.
- Mismo criterio de color que ya rige toda la app: los íconos de los
  estados vacíos usan tokens existentes, no colores nuevos.
- Cambiar el texto "Sin alertas activas." (Home y Alertas→Activas)
  rompe dos tests que hoy lo buscan literal
  (`src/__tests__/app/(vecino)/index.test.tsx` y
  `src/__tests__/app/(vecino)/alertas/index.test.tsx`) -- se actualizan
  junto con el cambio de copy, no es un hallazgo a resolver aparte.

## Decisiones ya tomadas

- **Dónde vive el saludo**: como texto nuevo dentro del contenido de
  `(vecino)/index.tsx` (arriba de la tarjeta "Mi departamento"), no
  como título del header del Drawer -- evita tocar la navegación
  (`Drawer.Screen options.title`) y mantiene "Mi Barrio+" como marca
  estable en el encabezado de todas las pantallas, igual que hoy.
- **Nombre a mostrar**: `membresia.first_name ?? membresia.nombre.split(" ")[0]`.
  Si ninguno de los dos existiera (no debería pasar, `nombre` no es
  opcional en el tipo), se omite el saludo entero en vez de mostrar
  algo roto.
- **Confirmación animada es temporal, no atada al ciclo de vida de
  `alertaEnviadaId`**: hoy `alertaEnviadaId` se setea al mandar la
  alerta y solo se vuelve a `null` si el residente cancela -- si se
  queda sin cancelar, sigue sin ser `null` para siempre (comportamiento
  actual, sin cambios). Atar la confirmación a esa misma condición la
  dejaría visible indefinidamente, que no es lo que un toast de
  confirmación debe hacer. La confirmación tiene su propio estado
  local con un `setTimeout` corto (variable del lado del
  implementador, pensar en el orden de 4-5 segundos) que la retira
  sola, independiente de que el residente cancele o no.
- **Ícono por pantalla vacía** (todos con el mismo componente
  reutilizable, ícono de Ionicons parametrizable):
  - Home / Alertas→Activas / Alertas→Historial: `shield-checkmark-outline`
    (ya transmite "todo tranquilo", coherente con el verde
    `fondoPositivo` que ya tienen esas tarjetas).
  - Avisos: `newspaper-outline`.
  - Números de emergencia: `call-outline`.
- **Texto de la confirmación de alerta**: título "Alerta enviada",
  subtítulo "Vecinos notificados" -- no "Conserjería fue notificada"
  (corrección del usuario: Empart no tiene conserjería, solo
  residentes, y así lo confirma `alertas/services.py:notificar_alerta`,
  que avisa a todo el condominio, no a un rol específico).
- **Mensajes** de estados vacíos: "Todo tranquilo por ahora" (alertas), "Todavía no hay
  avisos" (avisos), "Todavía no hay números cargados" (números de
  emergencia) -- tono consistente con el resto de los textos de la
  app (cercano, sin tecnicismo).
- **Color de fondo del estado vacío, por pantalla** (no es uno solo
  para las 5): `fondoPositivo` (verde) solo donde el mensaje es
  realmente tranquilizador -- Home/alertas-activas, Alertas→Activas,
  Alertas→Historial. Avisos y Números de emergencia no son "buenas
  noticias", son simplemente informativos y hoy no tienen ninguna
  tarjeta de color (listas sobre fondo blanco) -- usan `fondoInfo`
  (el mismo celeste de "Mi departamento"), no verde.
- **Tono del ícono**: `colores.accent` ("#0D9488") -- ya es el color
  usado para texto de "éxito"/confirmación en `condominio/index.tsx`,
  `perfil/index.tsx` y `numeros-emergencia/index.tsx`, es la elección
  más consistente con lo existente.

## Qué queda a criterio de quien implemente

- Nombre exacto y props del componente reutilizable de estado vacío
  (ícono + mensaje + tamaño), y del componente de confirmación
  animada (qué anima exactamente: fade, scale, o ambos -- los mockups
  mostraban una entrada con fade+slide y un pulso suave en el círculo
  del check).
- Duración exacta del auto-dismiss de la confirmación (sugerido 4-5s
  en Decisiones, no es un valor que el usuario haya fijado).
- Mecanismo exacto de la animación (`Animated` de React Native, mismo
  patrón ya usado en `BotonPanico` para la barra de progreso) vs.
  cualquier alternativa -- mientras no agregue una dependencia nueva
  de animación no mencionada acá.

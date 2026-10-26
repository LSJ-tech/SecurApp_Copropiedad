# Sistema visual para toda la app móvil + reordenamiento de la pantalla principal

## Intención y por qué

Probando la app en un dispositivo real, el usuario sintió que toda la app
se ve "plana" -- no una pantalla puntual con un problema, sino una
sensación general. Revisando el código se confirmó la causa: cada
pantalla (`donar`, `numeros-emergencia`, `perfil`, `avisos`, `directorio`,
`invitar`, `alertas`, `alertas/[id]`) repite el mismo patrón mínimo por
separado -- tarjetas con borde fino gris, filas separadas por una línea
(`borderBottomWidth: 1, borderBottomColor: "#eee"`), botones rectangulares
planos de un solo color, y el rojo de error (`#b00020`) escrito a mano en
cada archivo -- sin que exista ningún sistema de diseño compartido
(`app_movil/src/theme/colores.ts` hoy solo tiene 6 colores base, sin
tonos de fondo, sin un color de "peligro" formal).

Se armaron 3 mockups de dirección visual completa (no solo de la
pantalla principal) y el usuario eligió explícitamente la opción **B**:
tarjetas con un fondo de color suave distinto según su función (celeste
para información, durazno para apoyo/donación, verde para "todo bien"),
sin sombras ni bordes -- esa misma dirección se aplica a **todas** las
pantallas, no solo a la principal.

Además, para la pantalla principal específicamente, el usuario pidió
reordenarla: "Mi depto" arriba, seguido de "Donación", el botón de
pánico en el medio de la pantalla (ya no una franja fija arriba), y
"Alertas activas" al final.

## Goals

- Agregar a `app_movil/src/theme/colores.ts` los tokens de color que hoy
  faltan (ver D-01) y que de ahora en más se usan en **todas** las
  pantallas, reemplazando los literales sueltos (`#eee`, `#b00020`,
  bordes grises) que hoy están repetidos archivo por archivo.
- Reordenar `(vecino)/index.tsx`: Mi depto → Donación → botón de pánico
  (centrado, ya no franja fija arriba) → Alertas activas → Invitar
  vecinos (+ Directorio si es delegado).
- Aplicar el mismo sistema de tarjetas con color de fondo (sin bordes ni
  sombras) a las demás pantallas: `avisos`, `perfil`, `directorio`,
  `invitar`, `numeros-emergencia`, `alertas/index`, `alertas/[id]`.
- El botón de pánico mantiene exactamente su mecanismo (mantener
  presionado 2s, guardas, barra de progreso ya agregada en la iteración
  anterior) -- este trabajo es sobre estilo/posición, no sobre la lógica
  de alertas.

## Non-goals (fuera de esta fase, a propósito)

- La sección `(admin)` (Miembros, Torres, Unidades, Mi condominio --
  pantallas de devquad/delegado) -- el usuario probó y dio feedback
  sobre las pantallas de residente, no mencionó las de administración.
  Quedan con el estilo actual por ahora.
- Cambiar nada de la web -- esto es 100% del lado de la app móvil.
- Agregar animaciones o transiciones nuevas entre pantallas -- el pedido
  fue sobre color/forma de las tarjetas, no sobre movimiento.
- Cambiar la lógica de ninguna pantalla (qué datos trae, cuándo se
  recarga, qué pasa al tocar un botón) -- es un cambio de piel visual
  sobre comportamiento ya existente y ya probado.

## Anti-goals (qué haría esto un fracaso aunque "funcione")

- Que el botón de pánico dejado de ser inmediatamente reconocible o
  alcanzable al entrar a la pantalla por quedar "perdido" en el medio de
  tarjetas de colores -- sigue siendo el elemento más grande y de mayor
  contraste de la pantalla, aunque ya no esté fijo arriba.
- Que una lista larga (ej. el directorio de un condominio con 50+
  vecinos, o el historial de Avisos) se vuelva visualmente pesada por
  rellenar cada fila individual con un color sólido repetido 50 veces --
  ver D-03, el color de fondo es para tarjetas/resúmenes, no para cada
  fila de una lista larga.
- Que se pierda alguna de las correcciones ya hechas en la revisión
  final anterior (recarga al enfocar la pantalla, error distinto de
  "sin alertas", criterio de donación activa) -- este trabajo no toca
  esa lógica, solo el estilo.

## Constraints

- Mismas convenciones ya establecidas: TDD obligatorio, suite completa
  en verde antes de cada commit (`npm test` dentro de `app_movil/`).
- Reusar `app_movil/src/theme/colores.ts` como única fuente de los
  colores nuevos -- ninguna pantalla define un color de fondo/peligro
  suelto a partir de ahora, todas importan del theme.
- El mecanismo del botón de pánico (`BotonPanico.tsx`: `onPressIn`/
  `onPressOut`, el temporizador de 2s, la barra de progreso) no se
  toca -- solo su contenedor/posición dentro de `(vecino)/index.tsx` y,
  si hace falta, su tamaño/forma para que se vea bien centrado en vez de
  como franja de ancho completo.

## Decisiones (D-01..D-04)

**D-01 -- Tokens nuevos en `colores.ts`.**

```typescript
export const colores = {
  // ...los 6 que ya existen, sin cambios...
  peligro: "#b00020",        // ya se usaba igual, literal, en 6+ archivos
  apoyo: "#E07A3F",          // sólido -- para botones de la familia "apoyo" (Donar, Invitar)
  fondoInfo: "#EAF1F6",      // celeste -- tarjetas informativas
  fondoApoyo: "#FDF0E6",     // durazno -- tarjetas de donar/invitar
  fondoPositivo: "#F0F4EA",  // verde -- "todo bien" (sin alertas activas)
  fondoPeligro: "#FBE9E9",   // rojo tenue -- fila/tarjeta de una alerta ACTIVA real (no el botón en sí, que usa `peligro` sólido)
};
```

**D-02 -- Qué color le toca a cada pantalla (la categoría, no archivo por
archivo -- el plan decide los detalles de cada uno).**

- `fondoInfo` (celeste): Mi depto (home), Perfil, Directorio, Números de
  emergencia (la lista), datos informativos del detalle de una alerta.
- `fondoApoyo` (durazno): Donación (home y pantalla Donar), Invitar
  vecinos.
- `fondoPositivo` (verde): tarjeta de Alertas activas (home y pestaña
  Alertas) cuando está vacía/no hay ninguna.
- `peligro`/`fondoPeligro` (rojo): el botón de pánico en sí (sólido,
  `peligro`), y cualquier fila/tarjeta que represente una alerta
  realmente activa (fondo tenue `fondoPeligro`) -- tanto en la
  tarjeta-resumen de home como en la pestaña Alertas.
- Avisos no entra limpio en ninguna de las 3 categorías de arriba (no es
  ni apoyo ni alerta) -- se agrupa con `fondoInfo`, mismo criterio que
  Mi depto/Perfil/Directorio (información del condominio).

**D-03 -- Tarjetas con color sólo a nivel de tarjeta/resumen, nunca fila
por fila en una lista larga -- excepto "Activas" en Alertas.**

El mockup que eligió el usuario (opción B) mostraba 3 tarjetas de
sección, no una lista de muchos ítems. Para pantallas con listas
(Directorio, Avisos, Números de emergencia, el "Historial" dentro de
Alertas), aplicar el fondo de color a las tarjetas-resumen/vacías (ej.
"Sin alertas activas.", el encabezado de una sección) pero **no** a cada
fila individual de la lista -- esas quedan con fondo blanco/transparente,
separadas por espaciado en vez de línea divisoria, para que una lista de
50 vecinos no se vuelva 50 bloques de color repetidos (ver Anti-goals).
Dentro de una fila sí puede usarse el color como acento puntual (ej. un
punto o ícono del color de la categoría), nunca como relleno completo.

*Precisión tras el builder check:* esto choca, en apariencia, con D-02
("cualquier fila/tarjeta que represente una alerta realmente activa...
tanto en la tarjeta-resumen de home como en la pestaña Alertas" usa
`fondoPeligro`). Se resuelve separando las dos listas que hoy conviven
en `alertas/index.tsx` -- "Activas" (`activas`) y "Historial"
(`historial`, ver `ListaAlertasScreen`): **"Activas" es la excepción a
esta regla** -- cada fila SÍ lleva `fondoPeligro` de relleno completo
(manda D-02 ahí), porque en la práctica son 0-3 ítems y el color es
señal de urgencia real, no decoración de lista larga. **"Historial" sí
sigue la regla de este punto** (solo acento, nunca relleno completo),
porque ese sí puede acumular muchas filas con el tiempo.

**D-04 -- Pantalla principal: orden y botón de pánico centrado.**

Orden final de `(vecino)/index.tsx`, de arriba hacia abajo: franja
fija del *header* (sin cambios, fuera del área con scroll), y dentro del
contenido con scroll: 1) tarjeta "Mi depto" (`fondoInfo`), 2) tarjeta de
donación (`fondoApoyo`), 3) el botón de pánico -- ya no una franja de
ancho completo fija arriba, pasa a vivir **dentro** del área con scroll,
centrado horizontalmente, con un tamaño propio (ni un círculo gigante
como el diseño original, ni una franja de ancho completo como la
iteración anterior -- un tamaño intermedio, llamativo pero que no dejé
de convivir con las tarjetas alrededor), conservando su color sólido
`peligro`, el ícono, el degradé y la barra de progreso ya agregados en
la iteración anterior. *(Precisión tras el builder check: `SelectorTipoAlerta`,
el texto de error de un envío fallido, y `VentanaCancelar` son parte del
mismo mecanismo que el botón -- elegir el tipo es precondición para
disparar, y el error/la ventana de cancelar son la respuesta inmediata a
haber presionado. Los tres se mueven JUNTO con el botón como un mismo
bloque dentro del área con scroll -- selector arriba del botón, error y
ventana de cancelar debajo -- nunca separados de él por otra tarjeta, ni
uno fijo afuera del scroll y el otro adentro.)* 4) tarjeta de alertas activas (`fondoPositivo` si
vacía, `fondoPeligro` por cada alerta real listada). 5) "Invitar
vecinos", ahora también como tarjeta `fondoApoyo` (mismo trato visual
que "Donar", ya no un botón suelto) -- con "Directorio" debajo si el rol
es delegado, también como tarjeta pero `fondoInfo` (no `fondoApoyo`:
Directorio es informativo, mismo criterio de D-02 para esa pantalla,
aunque quede ubicado junto a Invitar). *(Decisión del redactor: el usuario no especificó dónde iba
"Invitar vecinos" en el reordenamiento -- queda al final por ser una
acción secundaria, agrupada con Donar por ser ambas "apoyo a la
comunidad", confirmado con el usuario en la conversación.)*

## Qué queda a criterio de quien lo construya

- Valores exactos de radio de borde, padding interno y tipografía de
  cada tarjeta nueva -- mientras seán consistentes entre pantallas
  (definir un estilo de tarjeta reusable es válido si simplifica el
  trabajo, mientras no cambie la estructura de datos/lógica de ninguna
  pantalla).
- Si el acento de color dentro de una fila de lista (ver D-03) es un
  ícono, un punto de color, o una línea lateral fina -- cualquiera que
  cumpla "nunca relleno completo" es válido.
- Tamaño exacto del botón de pánico centrado (D-04) -- queda a criterio
  mientras sea claramente el elemento más grande/llamativo de la
  pantalla.
- Orden de implementación entre pantallas (son independientes entre sí
  salvo que todas dependan de D-01 primero).

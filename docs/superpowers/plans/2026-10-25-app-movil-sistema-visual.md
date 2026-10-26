# Sistema visual para toda la app móvil + reordenamiento de la pantalla principal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> para implementar este plan tarea por tarea (decidido con el usuario, mismo
> método que los planes anteriores de esta sesión). Steps use checkbox
> (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar el patrón repetido de tarjeta-con-borde-fino/fila-con-línea
que hoy tiene cada pantalla de `(vecino)/` por un sistema de color
compartido (celeste=info, durazno=apoyo, verde=positivo, rojo=peligro), y
reordenar la pantalla principal con el botón de pánico centrado.

**Architecture:** Tokens de color nuevos en `theme/colores.ts` (D-01),
consumidos por 8 pantallas existentes sin tocar su lógica de datos/carga
-- cada tarea es un cambio de estilo puro sobre una pantalla ya probada.

**Tech Stack:** Expo/React Native + Jest/RTL, mismos patrones ya usados
en el proyecto.

**Spec:** `docs/superpowers/specs/2026-10-25-app-movil-sistema-visual-design.md`

## Global Constraints

- TDD obligatorio: cada paso de test se escribe y se corre en rojo antes
  del código que lo hace pasar.
- Suite completa en verde antes de cada commit: `npm test` dentro de
  `app_movil/`.
- Ninguna pantalla define un color de fondo/peligro suelto a partir de
  ahora -- todas importan de `theme/colores.ts` (D-01). Nunca repetir un
  hex literal nuevo en un archivo de pantalla.
- El mecanismo del botón de pánico (`BotonPanico.tsx`: `onPressIn`/
  `onPressOut`, el temporizador de 2s, la barra de progreso, el
  `testID="boton-panico"`) no se toca en ningún task -- solo su
  contenedor/tamaño dentro de `(vecino)/index.tsx`.
- Fondo de color a nivel de tarjeta/resumen, nunca por fila en una lista
  que puede crecer mucho (Directorio, Avisos, Números de emergencia,
  "Historial" de Alertas) -- excepto "Activas" en Alertas, que sí lleva
  relleno completo por fila (D-03, la excepción ya resuelta en el spec).

## Review Focus

- La lista "Historial" de Alertas con muchas filas no debe volverse
  visualmente pesada por relleno completo repetido -- cubierto en
  Task 9 (solo lleva acento, nunca fondo sólido).
- El bloque selector de tipo + botón de pánico + error + ventana de
  cancelar tiene que moverse junto como una unidad, nunca con otra
  tarjeta metida en el medio -- cubierto en Task 2.
- "Directorio" en la pantalla principal es `fondoInfo`, no `fondoApoyo`,
  aunque quede ubicado junto a "Invitar vecinos" -- cubierto en Task 2.
- El botón de pánico, aunque deje de ser una franja de ancho completo,
  tiene que seguir siendo el elemento más grande/contrastante de la
  pantalla (ver Anti-goals del spec) -- cubierto en Task 2 con una
  verificación explícita de que no se angosta a un tamaño chico.
- Las filas de "Activas" en Alertas sí llevan relleno completo
  `fondoPeligro` (es la excepción a la regla general) -- cubierto en
  Task 9, con un test que confirma la diferencia de tratamiento entre
  "Activas" e "Historial" en la misma pantalla.

---

### Task 1: Tokens de color nuevos en el theme

**Files:**
- Modify: `app_movil/src/theme/colores.ts`

**Interfaces:**
- Produces: `colores.peligro`, `colores.apoyo`, `colores.fondoInfo`,
  `colores.fondoApoyo`, `colores.fondoPositivo`, `colores.fondoPeligro`
  -- consumidos por Tasks 2-9.

- [ ] **Step 1: Agregar los tokens nuevos a `colores.ts`**

```typescript
export const colores = {
  primary: "#102D46",
  primaryDark: "#284E6B",
  primaryDarker: "#0A1B2A",
  secondary: "#708090",
  accent: "#0D9488",
  slate: "#5B7A8C",
  peligro: "#b00020",
  apoyo: "#E07A3F",
  fondoInfo: "#EAF1F6",
  fondoApoyo: "#FDF0E6",
  fondoPositivo: "#F0F4EA",
  fondoPeligro: "#FBE9E9",
};
```

No hace falta un test nuevo para esto -- es un archivo de constantes sin
comportamiento propio; lo prueban los tests de las pantallas que lo
consumen en las tareas siguientes.

- [ ] **Step 2: Correr la suite completa para confirmar que no rompe nada**

Run: `npm test` (dentro de `app_movil/`)
Expected: PASS, sin regresiones (nada usa los tokens nuevos todavía).

- [ ] **Step 3: Commit**

```bash
git add app_movil/src/theme/colores.ts
git commit -m "feat(mobile): agregar tokens de color del sistema visual compartido"
git push origin master
```

---

### Task 2: Pantalla principal -- reorden + botón centrado + tarjetas de color

**Files:**
- Modify: `app_movil/src/app/(vecino)/index.tsx`
- Modify: `app_movil/src/__tests__/app/(vecino)/index.test.tsx`

**Interfaces:**
- Consumes: tokens de Task 1.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al archivo de test existente (no tocar los 17 tests ya ahí):

```typescript
test("el orden de la pantalla es: mi depto, donación, botón de pánico, alertas activas, invitar", async () => {
  await render(<PantallaPanico />);
  await screen.findByText(/invitar vecinos/i);
  const texto = JSON.stringify(screen.toJSON());
  const posiciones = [
    texto.indexOf("Mi departamento"),
    texto.indexOf("Apoya el proyecto"),
    texto.indexOf("Mantén presionado"),
    texto.indexOf("Alertas activas"),
    texto.indexOf("Invitar vecinos"),
  ];
  expect(posiciones).toEqual([...posiciones].sort((a, b) => a - b));
});

test("el selector de tipo y el botón de pánico quedan juntos, sin otra tarjeta en el medio", async () => {
  await render(<PantallaPanico />);
  await screen.findByText(/invitar vecinos/i);
  const texto = JSON.stringify(screen.toJSON());
  const posSelector = texto.indexOf("Tipo de emergencia");
  const posBoton = texto.indexOf("Mantén presionado");
  const posAlertas = texto.indexOf("Alertas activas");
  expect(posSelector).toBeLessThan(posBoton);
  expect(posBoton).toBeLessThan(posAlertas);
});

test("la tarjeta de mi depto usa el color de fondo informativo", async () => {
  await render(<PantallaPanico />);
  const tarjeta = await screen.findByTestId("tarjeta-depto");
  expect(tarjeta.props.style).toEqual(expect.objectContaining({ backgroundColor: colores.fondoInfo }));
});

test("la tarjeta de donación usa el color de fondo de apoyo", async () => {
  await render(<PantallaPanico />);
  const tarjeta = await screen.findByTestId("tarjeta-donacion");
  expect(tarjeta.props.style).toEqual(expect.objectContaining({ backgroundColor: colores.fondoApoyo }));
});

test("la tarjeta de invitar vecinos usa el color de apoyo y la de directorio el informativo", async () => {
  mockUseAuth.mockReturnValue({
    membresia: {
      rol: "delegado",
      condominio: { id: 1, nombre: "Empart", etiqueta_torre: "Block", etiqueta_unidad: "Departamento", genero_unidad: "m" },
      unidad: null,
      nombre: "Logan", telefono: "",
    },
  });
  await render(<PantallaPanico />);
  const tarjetaInvitar = await screen.findByTestId("tarjeta-invitar");
  const tarjetaDirectorio = await screen.findByTestId("tarjeta-directorio");
  expect(tarjetaInvitar.props.style).toEqual(expect.objectContaining({ backgroundColor: colores.fondoApoyo }));
  expect(tarjetaDirectorio.props.style).toEqual(expect.objectContaining({ backgroundColor: colores.fondoInfo }));
});

test("sin alertas activas, la tarjeta usa el color positivo", async () => {
  await render(<PantallaPanico />);
  const tarjeta = await screen.findByTestId("tarjeta-alertas");
  expect(tarjeta.props.style).toEqual(expect.objectContaining({ backgroundColor: colores.fondoPositivo }));
});

test("el botón de pánico no se angosta a un tamaño chico al dejar de ser franja completa", async () => {
  await render(<PantallaPanico />);
  const boton = await screen.findByTestId("boton-panico");
  // No full-width (ya no franja) pero tampoco un tamaño mínimo chico --
  // sigue siendo el elemento más grande/llamativo de la pantalla.
  expect(boton.props.style).not.toEqual(expect.objectContaining({ width: "100%" }));
});
```

(Importar `colores` desde `@/theme/colores` al tope del archivo de test.)

- [ ] **Step 2: Correr los tests para confirmar que fallan**

Run: `npm test -- "\(vecino\)/index.test.tsx"`
Expected: FAIL -- faltan los `testID`s nuevos y el orden/colores todavía
no cambiaron.

- [ ] **Step 3: Reestructurar `(vecino)/index.tsx`**

Mover `BotonPanico`/`SelectorTipoAlerta`/`error`/`VentanaCancelar` DENTRO
del `ScrollView`, entre la tarjeta de donación y la de alertas activas
(ver D-04 del spec). Agregar `testID` a cada contenedor de tarjeta:
`tarjeta-depto`, `tarjeta-donacion`, `tarjeta-invitar`,
`tarjeta-directorio`, `tarjeta-alertas`. Aplicar los colores de fondo
(D-02): `fondoInfo` para depto/directorio, `fondoApoyo` para
donación/invitar, `fondoPositivo` o `fondoPeligro` para la tarjeta de
alertas según si `alertasActivas.length === 0` o no (si hay alertas
reales, la tarjeta en sí puede quedar `fondoPeligro` -- no hace falta
separar fila por fila acá porque es un resumen, no una lista completa
como la pestaña Alertas). "Invitar vecinos" y "Directorio" pasan de
`Pressable` sueltos a tarjetas con el mismo trato visual que las demás
(ver D-04). El botón de pánico centrado: achicar su ancho (ya no
`width: "100%"`) a un tamaño intermedio, mantener `colores.peligro`, el
ícono, el degradé y la barra de progreso de la iteración anterior sin
tocarlos.

- [ ] **Step 4: Correr los tests para confirmar que pasan**

Run: `npm test -- "\(vecino\)/index.test.tsx"`
Expected: PASS (24/24 -- los 17 ya existentes + los 7 nuevos).

- [ ] **Step 5: Correr la suite completa**

Run: `npm test`
Expected: PASS, sin regresiones.

- [ ] **Step 6: Commit**

```bash
git add "app_movil/src/app/(vecino)/index.tsx" "app_movil/src/__tests__/app/(vecino)/index.test.tsx"
git commit -m "feat(mobile): reordenar la pantalla principal con el botón de pánico centrado y tarjetas de color"
git push origin master
```

---

### Task 3: Donar -- tarjeta de apoyo

**Files:**
- Modify: `app_movil/src/app/(vecino)/donar/index.tsx`
- Modify: `app_movil/src/__tests__/app/(vecino)/donar/index.test.tsx`

**Interfaces:**
- Consumes: tokens de Task 1.

- [ ] **Step 1: Escribir el test que falla**

```typescript
test("la tarjeta principal usa el color de fondo de apoyo", async () => {
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({
    donacion_actual: null, pagos: [], total_donado: "0.00", cantidad_aportes: 0,
  });
  await render(<DonarScreen />);
  const tarjeta = await screen.findByTestId("tarjeta-donar");
  expect(tarjeta.props.style).toEqual(expect.objectContaining({ backgroundColor: colores.fondoApoyo }));
});
```

(Importar `colores` desde `@/theme/colores`.)

- [ ] **Step 2: Correr el test para confirmar que falla**

Run: `npm test -- "donar/index.test.tsx"`
Expected: FAIL -- no existe el `testID="tarjeta-donar"`.

- [ ] **Step 3: Aplicar `fondoApoyo` a la tarjeta principal en `donar/index.tsx`**

Agregar `testID="tarjeta-donar"` al `View` contenedor del bloque
donar/cancelar, y `backgroundColor: colores.fondoApoyo` (sin borde) a su
estilo.

- [ ] **Step 4: Correr el test para confirmar que pasa**

Run: `npm test -- "donar/index.test.tsx"`
Expected: PASS (todos, los viejos y el nuevo).

- [ ] **Step 5: Correr la suite completa**

Run: `npm test`
Expected: PASS, sin regresiones.

- [ ] **Step 6: Commit**

```bash
git add "app_movil/src/app/(vecino)/donar/index.tsx" "app_movil/src/__tests__/app/(vecino)/donar/index.test.tsx"
git commit -m "feat(mobile): tarjeta de color en la pantalla Donar"
git push origin master
```

---

### Task 4: Invitar -- tarjeta de apoyo

**Files:**
- Modify: `app_movil/src/app/(vecino)/invitar/index.tsx`
- Modify: `app_movil/src/__tests__/app/(vecino)/invitar/index.test.tsx`

**Interfaces:**
- Consumes: tokens de Task 1.

- [ ] **Step 1: Escribir el test que falla**

```typescript
test("la tarjeta principal usa el color de fondo de apoyo", async () => {
  jest.spyOn(invitacionApi, "obtenerInvitacion").mockResolvedValue({
    link_autoregistro: "https://x", mensaje_whatsapp_invitacion: "Te invito a...",
  });
  await render(<InvitarScreen />);
  const tarjeta = await screen.findByTestId("tarjeta-invitar");
  expect(tarjeta.props.style).toEqual(expect.objectContaining({ backgroundColor: colores.fondoApoyo }));
});
```

- [ ] **Step 2: Correr el test para confirmar que falla**

Run: `npm test -- "invitar/index.test.tsx"`
Expected: FAIL -- no existe el `testID="tarjeta-invitar"`.

- [ ] **Step 3: Envolver el contenido en una tarjeta `fondoApoyo` en `invitar/index.tsx`**

Agregar un `View` contenedor con `testID="tarjeta-invitar"` y
`backgroundColor: colores.fondoApoyo` alrededor del mensaje + botón
Compartir (sin cambiar la lógica de `manejarCompartir`).

- [ ] **Step 4: Correr el test para confirmar que pasa**

Run: `npm test -- "invitar/index.test.tsx"`
Expected: PASS (todos, los viejos y el nuevo).

- [ ] **Step 5: Correr la suite completa**

Run: `npm test`
Expected: PASS, sin regresiones.

- [ ] **Step 6: Commit**

```bash
git add "app_movil/src/app/(vecino)/invitar/index.tsx" "app_movil/src/__tests__/app/(vecino)/invitar/index.test.tsx"
git commit -m "feat(mobile): tarjeta de color en la pantalla Invitar"
git push origin master
```

---

### Task 5: Perfil -- tarjeta informativa

**Files:**
- Modify: `app_movil/src/app/(vecino)/perfil/index.tsx`
- Modify: `app_movil/src/__tests__/app/(vecino)/perfil/index.test.tsx`

**Interfaces:**
- Consumes: tokens de Task 1.

- [ ] **Step 1: Escribir el test que falla**

```typescript
test("el formulario principal usa el color de fondo informativo", async () => {
  jest.spyOn(authApi, "obtenerMiPerfil").mockResolvedValue({
    rol: "residente", condominio: { id: 1, nombre: "X" }, unidad: null,
    nombre: "Ana Pérez", telefono: "", first_name: "Ana", last_name: "Pérez", email: "ana@test.cl",
  });
  await render(<PantallaPerfil />);
  const tarjeta = await screen.findByTestId("tarjeta-perfil");
  expect(tarjeta.props.style).toEqual(expect.objectContaining({ backgroundColor: colores.fondoInfo }));
});
```

- [ ] **Step 2: Correr el test para confirmar que falla**

Run: `npm test -- "perfil/index.test.tsx"`
Expected: FAIL -- no existe el `testID="tarjeta-perfil"`.

- [ ] **Step 3: Envolver el formulario en una tarjeta `fondoInfo` en `perfil/index.tsx`**

Agregar un `View` contenedor con `testID="tarjeta-perfil"` y
`backgroundColor: colores.fondoInfo` alrededor de los `TextInput` del
formulario (los botones de Guardar/Cambiar contraseña/Eliminar cuenta
pueden quedar fuera de la tarjeta, como acciones, a criterio del
implementador).

- [ ] **Step 4: Correr el test para confirmar que pasa**

Run: `npm test -- "perfil/index.test.tsx"`
Expected: PASS (todos, los viejos y el nuevo).

- [ ] **Step 5: Correr la suite completa**

Run: `npm test`
Expected: PASS, sin regresiones.

- [ ] **Step 6: Commit**

```bash
git add "app_movil/src/app/(vecino)/perfil/index.tsx" "app_movil/src/__tests__/app/(vecino)/perfil/index.test.tsx"
git commit -m "feat(mobile): tarjeta de color en la pantalla Mi perfil"
git push origin master
```

---

### Task 6: Directorio -- color informativo, filas sin relleno

**Files:**
- Modify: `app_movil/src/app/(vecino)/directorio/index.tsx`
- Modify: `app_movil/src/__tests__/app/(vecino)/directorio/index.test.tsx`

**Interfaces:**
- Consumes: tokens de Task 1.

- [ ] **Step 1: Escribir el test que falla**

```typescript
test("cada fila no lleva un color de fondo sólido (D-03: solo acento, nunca relleno completo)", async () => {
  jest.spyOn(directorioApi, "listarDirectorio").mockResolvedValue([{ nombre: "Ana Pérez", torre: "A", unidad: "101" }]);
  await render(<DirectorioScreen />);
  const fila = await screen.findByTestId("fila-directorio-0");
  expect(fila.props.style).not.toEqual(expect.objectContaining({ backgroundColor: colores.fondoInfo }));
});
```

- [ ] **Step 2: Correr el test para confirmar que falla**

Run: `npm test -- "directorio/index.test.tsx"`
Expected: FAIL -- no existe el `testID="fila-directorio-0"`.

- [ ] **Step 3: Agregar `testID` por fila y un acento de color (ej. borde lateral `colores.fondoInfo`→borde `colores.primary` fino, o un punto de color) en `directorio/index.tsx`**

`testID={`fila-directorio-${indice}`}` en cada fila del `FlatList`
(usar el `indice` que ya trae `keyExtractor`). El acento es a criterio
del implementador (ver "Qué queda a criterio" del spec) -- nunca
`backgroundColor` de relleno completo con un token de fondo.

- [ ] **Step 4: Correr el test para confirmar que pasa**

Run: `npm test -- "directorio/index.test.tsx"`
Expected: PASS (todos, los viejos y el nuevo).

- [ ] **Step 5: Correr la suite completa**

Run: `npm test`
Expected: PASS, sin regresiones.

- [ ] **Step 6: Commit**

```bash
git add "app_movil/src/app/(vecino)/directorio/index.tsx" "app_movil/src/__tests__/app/(vecino)/directorio/index.test.tsx"
git commit -m "feat(mobile): acento de color en Directorio sin rellenar cada fila"
git push origin master
```

---

### Task 7: Avisos -- color informativo, filas sin relleno

**Files:**
- Modify: `app_movil/src/app/(vecino)/avisos/index.tsx`
- Modify: `app_movil/src/__tests__/app/(vecino)/avisos/index.test.tsx`
- Modify: `app_movil/src/__tests__/app/(vecino)/avisos/index.delegado.test.tsx`

**Interfaces:**
- Consumes: tokens de Task 1.

- [ ] **Step 1: Escribir los tests que fallan**

El archivo `index.test.tsx` ya mockea `useAuth` con rol `"residente"`
(no ve el formulario) -- el test de la tarjeta de color del formulario
va en `index.delegado.test.tsx`, que ya mockea rol `"delegado"` y sigue
el mismo patrón que sus 2 tests existentes:

```typescript
// en index.delegado.test.tsx
test("el formulario de publicar usa el color de fondo informativo", async () => {
  jest.spyOn(avisosApi, "listarAvisos").mockResolvedValue([]);
  await render(<ListaAvisosScreen />);
  await screen.findByText(/publicar aviso/i);
  const tarjeta = screen.getByTestId("tarjeta-formulario-aviso");
  expect(tarjeta.props.style).toEqual(expect.objectContaining({ backgroundColor: colores.fondoInfo }));
});
```

```typescript
// en index.test.tsx (rol residente -- no ve el formulario, pero sí la lista)
test("cada aviso de la lista no lleva un color de fondo sólido", async () => {
  jest.spyOn(avisosApi, "listarAvisos").mockResolvedValue([
    { id: 1, titulo: "A", cuerpo: "...", fecha_creacion: "2026-01-01T00:00:00Z", autor_nombre: null, torre_nombre: null, leido_por_count: null, total_destinatarios: null },
  ]);
  jest.spyOn(avisosApi, "marcarLeido").mockResolvedValue({} as any);
  await render(<ListaAvisosScreen />);
  const fila = await screen.findByTestId("fila-aviso-0");
  expect(fila.props.style).not.toEqual(expect.objectContaining({ backgroundColor: colores.fondoInfo }));
});
```

(Importar `colores` desde `@/theme/colores` en ambos archivos de test.)

- [ ] **Step 2: Correr los tests para confirmar que fallan**

Run: `npm test -- "avisos/index.test.tsx" "avisos/index.delegado.test.tsx"`
Expected: FAIL -- no existen los `testID`s nuevos.

- [ ] **Step 3: Aplicar `fondoInfo` al formulario y `testID` por fila en `avisos/index.tsx`**

`testID="tarjeta-formulario-aviso"` + `backgroundColor: colores.fondoInfo`
en el `View` que envuelve el formulario de publicar (visible solo para
delegado). `testID={`fila-aviso-${indice}`}` en cada fila del
`FlatList`, sin `backgroundColor` de relleno (acento opcional, mismo
criterio que Task 6).

- [ ] **Step 4: Correr los tests para confirmar que pasan**

Run: `npm test -- "avisos/index.test.tsx" "avisos/index.delegado.test.tsx"`
Expected: PASS (todos, los viejos y los nuevos en ambos archivos).

- [ ] **Step 5: Correr la suite completa**

Run: `npm test`
Expected: PASS, sin regresiones.

- [ ] **Step 6: Commit**

```bash
git add "app_movil/src/app/(vecino)/avisos/index.tsx" "app_movil/src/__tests__/app/(vecino)/avisos/"
git commit -m "feat(mobile): tarjeta de color en el formulario de Avisos, sin rellenar cada fila"
git push origin master
```

---

### Task 8: Números de emergencia -- color informativo, filas sin relleno

**Files:**
- Modify: `app_movil/src/app/(vecino)/numeros-emergencia/index.tsx`
- Modify: `app_movil/src/__tests__/app/(vecino)/numeros-emergencia/index.test.tsx`

**Interfaces:**
- Consumes: tokens de Task 1.

- [ ] **Step 1: Escribir el test que falla**

```typescript
test("cada número de la lista no lleva un color de fondo sólido", async () => {
  jest.spyOn(numerosApi, "listarNumerosEmergencia").mockResolvedValue([
    { id: 1, categoria: "bomberos", categoria_display: "Bomberos", nombre: "Bomberos", telefono: "132", es_nacional: true },
  ]);
  jest.spyOn(numerosApi, "listarMisPropuestas").mockResolvedValue([]);
  await render(<NumerosEmergenciaScreen />);
  const fila = await screen.findByTestId("fila-numero-0");
  expect(fila.props.style).not.toEqual(expect.objectContaining({ backgroundColor: colores.fondoInfo }));
});
```

- [ ] **Step 2: Correr el test para confirmar que falla**

Run: `npm test -- "numeros-emergencia/index.test.tsx"`
Expected: FAIL -- no existe el `testID="fila-numero-0"`.

- [ ] **Step 3: Agregar `testID` por fila y un acento de color en `numeros-emergencia/index.tsx`**

`testID={`fila-numero-${indice}`}` en cada fila de la lista de
números (usar el índice del `.map`). Mismo criterio que Task 6/7: acento
puntual, nunca relleno completo del color `fondoInfo`.

- [ ] **Step 4: Correr el test para confirmar que pasa**

Run: `npm test -- "numeros-emergencia/index.test.tsx"`
Expected: PASS (todos, los viejos y el nuevo).

- [ ] **Step 5: Correr la suite completa**

Run: `npm test`
Expected: PASS, sin regresiones.

- [ ] **Step 6: Commit**

```bash
git add "app_movil/src/app/(vecino)/numeros-emergencia/index.tsx" "app_movil/src/__tests__/app/(vecino)/numeros-emergencia/index.test.tsx"
git commit -m "feat(mobile): acento de color en Números de emergencia sin rellenar cada fila"
git push origin master
```

---

### Task 9: Alertas -- Activas con relleno completo (excepción), Historial con acento, detalle informativo

**Files:**
- Modify: `app_movil/src/app/(vecino)/alertas/index.tsx`
- Modify: `app_movil/src/app/(vecino)/alertas/[id].tsx`
- Modify: `app_movil/src/__tests__/app/(vecino)/alertas/index.test.tsx`
- Modify: `app_movil/src/__tests__/app/(vecino)/alertas/[id].test.tsx`

**Interfaces:**
- Consumes: tokens de Task 1.

- [ ] **Step 1: Escribir los tests que fallan**

En `alertas/index.test.tsx`:

```typescript
test("una fila de Activas lleva el color de fondo de peligro (excepción a la regla general)", async () => {
  jest.spyOn(alertasApi, "listarAlertas").mockImplementation((estado) =>
    Promise.resolve(estado === "activa" ? [{ id: 1, tipo_display: "Robo", estado: "activa", estado_display: "Activa" } as any] : [])
  );
  await render(<ListaAlertasScreen />);
  const fila = await screen.findByTestId("fila-activa-0");
  expect(fila.props.style).toEqual(expect.objectContaining({ backgroundColor: colores.fondoPeligro }));
});

test("una fila de Historial NO lleva relleno completo (sigue la regla general de D-03)", async () => {
  jest.spyOn(alertasApi, "listarAlertas").mockImplementation((estado) =>
    Promise.resolve(estado === "recientes" ? [{ id: 2, tipo_display: "Incendio", estado: "resuelta", estado_display: "Resuelta" } as any] : [])
  );
  await render(<ListaAlertasScreen />);
  const fila = await screen.findByTestId("fila-historial-0");
  expect(fila.props.style).not.toEqual(expect.objectContaining({ backgroundColor: colores.fondoPeligro }));
});
```

En `alertas/[id].test.tsx`:

```typescript
test("el bloque de datos de la alerta usa el color de fondo informativo", async () => {
  jest.spyOn(alertasApi, "obtenerAlerta").mockResolvedValue({
    id: 7, tipo_display: "Robo", estado: "activa", estado_display: "Activa", mensaje: "", autor_nombre: "Ana", visto_por_count: null,
  } as any);
  await render(<DetalleAlertaScreen />);
  const tarjeta = await screen.findByTestId("tarjeta-detalle-alerta");
  expect(tarjeta.props.style).toEqual(expect.objectContaining({ backgroundColor: colores.fondoInfo }));
});
```

- [ ] **Step 2: Correr los tests para confirmar que fallan**

Run: `npm test -- "alertas/index.test.tsx" "alertas/[id].test.tsx"`
Expected: FAIL -- no existen los `testID`s nuevos.

- [ ] **Step 3: Diferenciar el estilo de `Fila` por sección en `alertas/index.tsx`**

El componente `Fila` (hoy compartido entre Activas e Historial) necesita
distinguir cuál lista lo está renderizando -- agregar una prop
`variante: "activa" | "historial"` (o renderizar dos variantes de fila
separadas, a criterio). `testID={`fila-${variante}-${indice}`}`.
Variante `"activa"`: `backgroundColor: colores.fondoPeligro` de relleno
completo. Variante `"historial"`: sin `backgroundColor` de relleno,
acento opcional (mismo criterio que Tasks 6-8).

- [ ] **Step 4: Envolver el bloque de datos en una tarjeta `fondoInfo` en `alertas/[id].tsx`**

`testID="tarjeta-detalle-alerta"` + `backgroundColor: colores.fondoInfo`
alrededor de los `<Text>` de tipo/estado/reportada por/mensaje/visto por
(el botón "Marcar como visto" puede quedar fuera, como acción).

- [ ] **Step 5: Correr los tests para confirmar que pasan**

Run: `npm test -- "alertas/index.test.tsx" "alertas/[id].test.tsx"`
Expected: PASS (todos, los viejos y los nuevos).

- [ ] **Step 6: Correr la suite completa**

Run: `npm test`
Expected: PASS, sin regresiones.

- [ ] **Step 7: Commit**

```bash
git add "app_movil/src/app/(vecino)/alertas/" "app_movil/src/__tests__/app/(vecino)/alertas/"
git commit -m "feat(mobile): Activas con color de peligro por fila (excepción), Historial y detalle con el sistema visual"
git push origin master
```

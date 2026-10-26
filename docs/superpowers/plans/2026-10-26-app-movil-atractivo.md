# App móvil Mi Barrio+: microinteracciones + estados vacíos ilustrados -- Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar el "no pasa nada" silencioso de la app móvil por una confirmación visible al mandar una alerta (con vibración), un saludo personalizado en el home, y estados vacíos con ícono en las cinco listas que hoy quedan en texto plano o en blanco.

**Architecture:** Dos componentes reutilizables nuevos (`EstadoVacioIlustrado`, `ConfirmacionAnimada`) se insertan en las pantallas existentes sin tocar su lógica de datos. `ConfirmacionAnimada` sigue el mismo patrón de auto-ocultamiento por `key` que ya usa `VentanaCancelar` en la misma pantalla.

**Tech Stack:** Expo/React Native, TypeScript, Expo Router, jest-expo, `@expo/vector-icons` (ya instalado), `expo-haptics` (se agrega en Task 2).

**Spec:** `docs/superpowers/specs/2026-10-26-app-movil-atractivo-design.md`

## Global Constraints

- Color del ícono en los estados vacíos: `colores.accent` ("#0D9488").
- Estados vacíos "buena noticia" (verde, `colores.fondoPositivo`): Home/alertas-activas, Alertas→Activas, Alertas→Historial, ícono `shield-checkmark-outline`, mensaje **"Todo tranquilo por ahora"**.
- Estados vacíos informativos (celeste, `colores.fondoInfo`): Avisos (ícono `newspaper-outline`, mensaje **"Todavía no hay avisos"**), Números de emergencia (ícono `call-outline`, mensaje **"Todavía no hay números cargados"**).
- Texto de la confirmación de alerta: título **"Alerta enviada"**, subtítulo **"Vecinos notificados"**.
- `expo-haptics` no está enlazado en los builds de dev client ya instalados (emulador, iPhone de prueba) -- toda llamada a `Haptics.notificationAsync` va con `.catch(() => {})`, nunca puede tirar la UI de confirmación.
- El botón de pánico (`BotonPanico.tsx`) no se toca.
- `npx jest` confirmado en verde en 40/40 suites antes de empezar (último estado conocido de la sesión).

## Review Focus

- El saludo no debe romper mientras `membresia` todavía no cargó (`useAuth()` empieza con `membresia: null`) -- probado en Task 3.
- `ConfirmacionAnimada` desmontada antes de que termine su temporizador (el residente navega a otra pestaña del Drawer apenas mandó la alerta) no debe generar un warning de "state update on unmounted component" -- probado en Task 2, mismo patrón que la revisión final ya aplicó a `BotonPanico`.
- Si `Haptics.notificationAsync` rechaza (módulo nativo no enlazado todavía), la tarjeta de confirmación visual igual tiene que aparecer -- probado en Task 2.
- El formulario de publicar aviso (solo delegado) no debe desaparecer ni esconderse cuando la lista de avisos está vacía -- probado en Task 5.
- En Números de emergencia, que la lista de números esté vacía no debe ocultar "Mis propuestas" cuando sí hay propuestas propias cargadas -- probado en Task 6.

---

### Task 1: `EstadoVacioIlustrado`

**Files:**
- Create: `app_movil/src/components/EstadoVacioIlustrado.tsx`
- Test: `app_movil/src/components/EstadoVacioIlustrado.test.tsx`

**Interfaces:**
- Produces: `EstadoVacioIlustrado({ icono, mensaje, testID }: { icono: ComponentProps<typeof Ionicons>["name"]; mensaje: string; testID?: string })` -- componente sin color de fondo propio (ni padding de tarjeta): solo ícono (Ionicons, `size=40`, `color=colores.accent`, con `testID="${testID}-icono"` cuando se pasa `testID`) + `Text` con `mensaje`, centrados. El color/tarjeta que lo envuelve lo decide cada pantalla que lo usa (Tasks 3-6), igual que ya hace cada pantalla con su propio `testID="tarjeta-*"`.

- [ ] **Step 1: Write the failing test**

```tsx
import { render, screen } from "@testing-library/react-native";
import { EstadoVacioIlustrado } from "./EstadoVacioIlustrado";

test("muestra el ícono y el mensaje dados", async () => {
  await render(<EstadoVacioIlustrado testID="estado-prueba" icono="newspaper-outline" mensaje="Todavía no hay avisos" />);
  expect(screen.getByTestId("estado-prueba-icono").props.name).toBe("newspaper-outline");
  await screen.findByText("Todavía no hay avisos");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest src/components/EstadoVacioIlustrado.test.tsx`
Expected: FAIL -- no se puede resolver el módulo `./EstadoVacioIlustrado`.

- [ ] **Step 3: Implement `EstadoVacioIlustrado` en `app_movil/src/components/EstadoVacioIlustrado.tsx`**

Usa `Ionicons` de `@expo/vector-icons` (mismo import que `SelectorTipoAlerta.tsx`) y `colores` de `@/theme/colores`. `View` contenedor con `alignItems:"center"`, `gap` chico entre ícono y texto; `Text` con `textAlign:"center"`, color `colores.secondary` o similar neutro (no `colores.accent`, ese es solo para el ícono).

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest src/components/EstadoVacioIlustrado.test.tsx`
Expected: PASS 1/1

- [ ] **Step 5: Commit**

```bash
git add app_movil/src/components/EstadoVacioIlustrado.tsx app_movil/src/components/EstadoVacioIlustrado.test.tsx
git commit -m "App móvil: agrega EstadoVacioIlustrado (ícono + mensaje reutilizable)"
git push origin master
```

---

### Task 2: `ConfirmacionAnimada`

**Files:**
- Create: `app_movil/src/components/ConfirmacionAnimada.tsx`
- Test: `app_movil/src/components/ConfirmacionAnimada.test.tsx`
- Modify: `app_movil/package.json`, `app_movil/package-lock.json` (dependencia `expo-haptics`, ya agregada en esta sesión vía `npx expo install expo-haptics` -- confirmar que sigue en el `package.json` antes de este task, no reinstalar si ya está)

**Interfaces:**
- Produces: `ConfirmacionAnimada({ titulo, subtitulo }: { titulo: string; subtitulo?: string })`. Se monta con `key` (igual que `VentanaCancelar` ya se usa con `key={alertaEnviadaId}`) para que cada alerta nueva dispare una instancia fresca. Internamente: al montar, dispara `Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {})` y una animación de entrada (`Animated.Value` + `Animated.timing(..., { useNativeDriver: true })`, mismo patrón que `BotonPanico.tsx`); un `setTimeout` de **4500 ms** pone un estado interno `visible` en `false` (deja de renderizar, sin avisarle a quien lo usa -- mismo criterio que el auto-ocultamiento de `VentanaCancelar`); limpia el timeout y para la animación al desmontar.

- [ ] **Step 1: Write the failing tests**

```tsx
import { act, render, screen } from "@testing-library/react-native";
import * as Haptics from "expo-haptics";
import { ConfirmacionAnimada } from "./ConfirmacionAnimada";

test("muestra título y subtítulo al montar", async () => {
  await render(<ConfirmacionAnimada titulo="Alerta enviada" subtitulo="Vecinos notificados" />);
  await screen.findByText("Alerta enviada");
  await screen.findByText("Vecinos notificados");
});

test("sin subtítulo, no revienta y no lo muestra", async () => {
  await render(<ConfirmacionAnimada titulo="Alerta enviada" />);
  await screen.findByText("Alerta enviada");
});

test("se retira sola pasado el tiempo", async () => {
  jest.useFakeTimers();
  await render(<ConfirmacionAnimada titulo="Alerta enviada" />);
  await screen.findByText("Alerta enviada");
  await act(async () => {
    await jest.advanceTimersByTimeAsync(5000);
  });
  jest.useRealTimers();
  expect(screen.queryByText("Alerta enviada")).toBeNull();
});

test("llama a la vibración de éxito al montar", async () => {
  const spy = jest.spyOn(Haptics, "notificationAsync").mockResolvedValue();
  await render(<ConfirmacionAnimada titulo="Alerta enviada" />);
  expect(spy).toHaveBeenCalledWith(Haptics.NotificationFeedbackType.Success);
});

test("si la vibración falla, la confirmación visual igual se muestra", async () => {
  jest.spyOn(Haptics, "notificationAsync").mockRejectedValue(new Error("no linked"));
  await render(<ConfirmacionAnimada titulo="Alerta enviada" />);
  await screen.findByText("Alerta enviada");
});

test("si se desmonta mientras tanto, no revienta ni deja un timer colgado", async () => {
  const { unmount } = await render(<ConfirmacionAnimada titulo="Alerta enviada" />);
  await screen.findByText("Alerta enviada");
  expect(() => unmount()).not.toThrow();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx jest src/components/ConfirmacionAnimada.test.tsx`
Expected: FAIL -- no se puede resolver el módulo `./ConfirmacionAnimada`.

- [ ] **Step 3: Implementar `ConfirmacionAnimada` en `app_movil/src/components/ConfirmacionAnimada.tsx`**

Estructura: círculo con ícono `Ionicons name="checkmark" color="#fff"` sobre fondo `colores.accent`, junto a `Text` título (bold, `colores.primary`) y `Text` subtítulo (si viene, `colores.secondary`) debajo. Tarjeta contenedora con `backgroundColor: colores.fondoPositivo`, `borderRadius`, padding -- mismo lenguaje visual que las demás tarjetas de la app. `useRef` para el id del `setTimeout` (mismo patrón que `temporizador.current` en `BotonPanico.tsx`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx jest src/components/ConfirmacionAnimada.test.tsx`
Expected: PASS 6/6

- [ ] **Step 5: Commit**

```bash
git add app_movil/src/components/ConfirmacionAnimada.tsx app_movil/src/components/ConfirmacionAnimada.test.tsx app_movil/package.json app_movil/package-lock.json
git commit -m "App móvil: agrega ConfirmacionAnimada (confirmación con vibración al mandar una alerta)"
git push origin master
```

---

### Task 3: Home -- saludo, confirmación animada, estado vacío de alertas

**Files:**
- Modify: `app_movil/src/app/(vecino)/index.tsx`
- Modify: `app_movil/src/__tests__/app/(vecino)/index.test.tsx`

**Interfaces:**
- Consumes: `EstadoVacioIlustrado` (Task 1), `ConfirmacionAnimada` (Task 2), `membresia.first_name?: string` y `membresia.nombre: string` (ya existentes en `MembresiaOut`, `app_movil/src/api/auth.ts`).

- [ ] **Step 1: Write the failing tests**

Agregar a `index.test.tsx` (mismo archivo, mismos mocks ya presentes en `beforeEach`):

```tsx
test("saluda por el nombre de pila del residente", async () => {
  await render(<PantallaPanico />);
  await screen.findByText(/hola, logan/i);
});

test("si no hay first_name, usa la primera palabra de nombre", async () => {
  mockUseAuth.mockReturnValue({
    membresia: {
      rol: "residente",
      condominio: { id: 1, nombre: "Empart", etiqueta_torre: "Block", etiqueta_unidad: "Departamento", genero_unidad: "m" },
      unidad: null,
      nombre: "Logan Silva Jara", telefono: "",
    },
  });
  await render(<PantallaPanico />);
  await screen.findByText(/hola, logan\b/i);
  expect(screen.queryByText(/silva/i)).toBeNull();
});

test("mientras la membresía no cargó, no muestra un saludo roto", async () => {
  mockUseAuth.mockReturnValue({ membresia: null });
  await render(<PantallaPanico />);
  expect(screen.queryByText(/hola,/i)).toBeNull();
});

test("al confirmar el envío, aparece la confirmación animada", async () => {
  jest.spyOn(enviarAlertaModulo, "enviarAlerta").mockResolvedValue({ id: 1 } as any);
  await render(<PantallaPanico />);
  jest.useFakeTimers();
  const boton = screen.getByTestId("boton-panico");
  await fireEvent(boton, "pressIn");
  await act(async () => {
    await jest.advanceTimersByTimeAsync(2000);
  });
  jest.useRealTimers();
  await screen.findByText("Alerta enviada");
  await screen.findByText("Vecinos notificados");
});

test("sin alertas activas, muestra el estado vacío ilustrado", async () => {
  await render(<PantallaPanico />);
  await screen.findByText(/todo tranquilo por ahora/i);
});
```

Actualizar los dos tests existentes que hoy buscan el texto literal "Sin alertas activas." (`sin alertas activas, muestra 'Sin alertas activas.'` y `si falla cargar las alertas activas, muestra un error en vez de 'Sin alertas activas.'`) para esperar `/todo tranquilo por ahora/i` en vez del texto viejo.

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx jest "src/__tests__/app/(vecino)/index.test.tsx"`
Expected: FAIL -- los 5 tests nuevos fallan (sin saludo, sin confirmación, texto viejo todavía presente); los 2 actualizados fallan contra el texto nuevo que todavía no existe.

- [ ] **Step 3: Modificar `app_movil/src/app/(vecino)/index.tsx`**

- Import `EstadoVacioIlustrado` y `ConfirmacionAnimada`.
- Antes de la tarjeta `tarjeta-depto`: `const primerNombre = membresia?.first_name ?? membresia?.nombre?.split(" ")[0];` y, si existe, `<Text style={styles.saludo}>Hola, {primerNombre} 👋</Text>`.
- Dentro de `tarjeta-alertas`, reemplazar `<Text>Sin alertas activas.</Text>` por `<EstadoVacioIlustrado testID="estado-vacio-alertas-home" icono="shield-checkmark-outline" mensaje="Todo tranquilo por ahora" />`.
- Dentro del bloque `alertaEnviadaId !== null` (junto a `VentanaCancelar`, antes de él): `<ConfirmacionAnimada key={alertaEnviadaId} titulo="Alerta enviada" subtitulo="Vecinos notificados" />`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx jest "src/__tests__/app/(vecino)/index.test.tsx"`
Expected: PASS (todos los tests del archivo, viejos y nuevos)

- [ ] **Step 5: Commit**

```bash
git add "app_movil/src/app/(vecino)/index.tsx" "app_movil/src/__tests__/app/(vecino)/index.test.tsx"
git commit -m "App móvil: home saluda por nombre y confirma el envío de alerta con animación"
git push origin master
```

---

### Task 4: Alertas -- estado vacío ilustrado en Activas e Historial

**Files:**
- Modify: `app_movil/src/app/(vecino)/alertas/index.tsx`
- Modify: `app_movil/src/__tests__/app/(vecino)/alertas/index.test.tsx`

**Interfaces:**
- Consumes: `EstadoVacioIlustrado` (Task 1).

- [ ] **Step 1: Write the failing test**

```tsx
test("historial vacío muestra el estado vacío ilustrado, no queda en blanco", async () => {
  jest.spyOn(alertasApi, "listarAlertas").mockResolvedValue([]);
  await render(<ListaAlertasScreen />);
  const tarjeta = await screen.findByTestId("tarjeta-sin-historial");
  expect(tarjeta.props.style).toEqual(
    expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.fondoPositivo })])
  );
  await screen.findByText(/todo tranquilo por ahora/i);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx jest "src/__tests__/app/(vecino)/alertas/index.test.tsx"`
Expected: FAIL -- no existe `tarjeta-sin-historial` (hoy la lista vacía no renderiza nada).

- [ ] **Step 3: Modificar `app_movil/src/app/(vecino)/alertas/index.tsx`**

- Dentro de `tarjeta-sin-activas` (ya existe, `fondoPositivo`), reemplazar `<Text>Sin alertas activas.</Text>` por `<EstadoVacioIlustrado testID="estado-vacio-alertas-activas" icono="shield-checkmark-outline" mensaje="Todo tranquilo por ahora" />`.
- Agregar el mismo patrón para Historial: si `historial.length === 0`, en vez del `FlatList` vacío, `<View testID="tarjeta-sin-historial" style={[styles.tarjeta, { backgroundColor: colores.fondoPositivo }]}><EstadoVacioIlustrado testID="estado-vacio-alertas-historial" icono="shield-checkmark-outline" mensaje="Todo tranquilo por ahora" /></View>`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx jest "src/__tests__/app/(vecino)/alertas/index.test.tsx"`
Expected: PASS (todos los tests del archivo)

- [ ] **Step 5: Commit**

```bash
git add "app_movil/src/app/(vecino)/alertas/index.tsx" "app_movil/src/__tests__/app/(vecino)/alertas/index.test.tsx"
git commit -m "App móvil: Alertas -- Historial vacío ya no queda en blanco"
git push origin master
```

---

### Task 5: Avisos -- estado vacío ilustrado

**Files:**
- Modify: `app_movil/src/app/(vecino)/avisos/index.tsx`
- Modify: `app_movil/src/__tests__/app/(vecino)/avisos/index.test.tsx` (mockea `rol: "residente"` a nivel de módulo)
- Modify: `app_movil/src/__tests__/app/(vecino)/avisos/index.delegado.test.tsx` (mockea `rol: "delegado"` a nivel de módulo)

**Interfaces:**
- Consumes: `EstadoVacioIlustrado` (Task 1).

- [ ] **Step 1: Write the failing tests**

```tsx
test("sin avisos, muestra el estado vacío ilustrado en vez de quedar en blanco", async () => {
  jest.spyOn(avisosApi, "listarAvisos").mockResolvedValue([]);
  await render(<ListaAvisosScreen />);
  const tarjeta = await screen.findByTestId("tarjeta-sin-avisos");
  expect(tarjeta.props.style).toEqual(
    expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.fondoInfo })])
  );
  await screen.findByText(/todavía no hay avisos/i);
});

test("delegado sin avisos igual ve el formulario de publicar", async () => {
  jest.spyOn(avisosApi, "listarAvisos").mockResolvedValue([]);
  await render(<ListaAvisosScreen />);
  await screen.findByTestId("tarjeta-formulario-aviso");
  await screen.findByTestId("tarjeta-sin-avisos");
});
```

El primer test (estado vacío general) va en `index.test.tsx` (ya mockea `rol: "residente"` a nivel de módulo). El segundo (`"delegado sin avisos..."`) va en `index.delegado.test.tsx` (ya mockea `rol: "delegado"` a nivel de módulo) -- ninguno de los dos archivos permite cambiar el rol por test, son mocks estáticos de módulo.

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx jest "src/__tests__/app/(vecino)/avisos/"`
Expected: FAIL -- no existe `tarjeta-sin-avisos`.

- [ ] **Step 3: Modificar `app_movil/src/app/(vecino)/avisos/index.tsx`**

`FlatList` ya tiene `data={avisos}` -- agregar `ListEmptyComponent={<View testID="tarjeta-sin-avisos" style={[styles.tarjetaVacia, { backgroundColor: colores.fondoInfo }]}><EstadoVacioIlustrado testID="estado-vacio-avisos" icono="newspaper-outline" mensaje="Todavía no hay avisos" /></View>}`. El formulario de publicar (bloque `membresia?.rol === "delegado"`) queda intacto, fuera y antes del `FlatList` -- no se toca.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx jest "src/__tests__/app/(vecino)/avisos/"`
Expected: PASS (todos los tests de la carpeta)

- [ ] **Step 5: Commit**

```bash
git add "app_movil/src/app/(vecino)/avisos/index.tsx" "app_movil/src/__tests__/app/(vecino)/avisos/"
git commit -m "App móvil: Avisos -- estado vacío ilustrado en vez de pantalla en blanco"
git push origin master
```

---

### Task 6: Números de emergencia -- estado vacío ilustrado

**Files:**
- Modify: `app_movil/src/app/(vecino)/numeros-emergencia/index.tsx`
- Modify: `app_movil/src/__tests__/app/(vecino)/numeros-emergencia/index.test.tsx`

**Interfaces:**
- Consumes: `EstadoVacioIlustrado` (Task 1).

- [ ] **Step 1: Write the failing tests**

```tsx
test("sin números cargados, muestra el estado vacío ilustrado en vez de quedar en blanco", async () => {
  jest.spyOn(numerosApi, "listarNumerosEmergencia").mockResolvedValue([]);
  jest.spyOn(numerosApi, "listarMisPropuestas").mockResolvedValue([]);
  await render(<NumerosEmergenciaScreen />);
  const tarjeta = await screen.findByTestId("tarjeta-sin-numeros");
  expect(tarjeta.props.style).toEqual(
    expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.fondoInfo })])
  );
  await screen.findByText(/todavía no hay números cargados/i);
});

test("sin números pero con una propuesta propia, se ven ambas cosas", async () => {
  jest.spyOn(numerosApi, "listarNumerosEmergencia").mockResolvedValue([]);
  jest.spyOn(numerosApi, "listarMisPropuestas").mockResolvedValue([
    { id: 1, nombre: "Plomero", estado_display: "Pendiente" } as any,
  ]);
  await render(<NumerosEmergenciaScreen />);
  await screen.findByTestId("tarjeta-sin-numeros");
  await screen.findByText("Plomero");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx jest "src/__tests__/app/(vecino)/numeros-emergencia/"`
Expected: FAIL -- no existe `tarjeta-sin-numeros`.

- [ ] **Step 3: Modificar `app_movil/src/app/(vecino)/numeros-emergencia/index.tsx`**

Antes (o en vez) del `numeros.map(...)`: `{numeros.length === 0 ? (<View testID="tarjeta-sin-numeros" style={[styles.tarjetaVacia, { backgroundColor: colores.fondoInfo }]}><EstadoVacioIlustrado testID="estado-vacio-numeros" icono="call-outline" mensaje="Todavía no hay números cargados" /></View>) : (numeros.map(...) tal como está hoy)}`. El bloque `misPropuestas.length > 0 && (...)` que sigue queda sin cambios, fuera de esta condición.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx jest "src/__tests__/app/(vecino)/numeros-emergencia/"`
Expected: PASS (todos los tests del archivo)

- [ ] **Step 5: Commit**

```bash
git add "app_movil/src/app/(vecino)/numeros-emergencia/index.tsx" "app_movil/src/__tests__/app/(vecino)/numeros-emergencia/"
git commit -m "App móvil: Números de emergencia -- estado vacío ilustrado en vez de pantalla en blanco"
git push origin master
```

---

## Final check

- [ ] `npx jest` (suite completa) en verde.
- [ ] `npx tsc --noEmit` (o el chequeo de tipos que use el proyecto) sin errores nuevos.

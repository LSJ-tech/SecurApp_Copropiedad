# App móvil de Mi Barrio+ -- Tanda 3 (Modo administrador) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir D-07 -- el modo administrador de devquad, separado del menú del vecino: elegir en qué condominio operar, y gestionar miembros/torres/unidades y "Mi condominio" desde el celular. Al terminar, una cuenta devquad puede hacer en la app lo mismo que hoy hace en el panel web para administrar un condominio (salvo "mover miembro entre condominios", explícitamente fuera de esta tanda -- ver Non-goals).

**Architecture:** Reestructura `AuthContext` (Tanda 1) para que una cuenta devquad (login con `membresia: null`) ya no caiga en un callejón sin salida ("sin-membresia", Tanda 1) sino en un flujo real: elegir condominio (`DevquadCondominiosApiView`/`DevquadEntrarCondominioApiView`, ya construidos en la Fase 1) y entrar a una sección separada de la app (`app/(admin)/`), con su propio Drawer, sin compartir navegación con `(vecino)/` (D-07). Cada pantalla de gestión sigue el mismo patrón ya probado en las Tandas 1-2: un módulo `api/<recurso>.ts`, una pantalla, `.catch` en toda promesa, errores de validación mostrados vía `ErrorDeServidor.body` (Tanda 2).

**Tech Stack:** El mismo de las Tandas 1-2. Sin paquetes nuevos.

**Spec:** `docs/superpowers/specs/2026-10-19-app-movil-mi-barrio-design.md`, D-07 y "Cómo se construye" (tanda 3: "elegir condominio, miembros/torres/unidades, Mi condominio").

## Global Constraints

- Backend: no se toca nada -- `DevquadCondominiosApiView`, `DevquadEntrarCondominioApiView`, `TorreViewSet`, `UnidadViewSet`, `MembresiaViewSet`, `CondominioView`, `RegenerarTokenApiView` ya existen y ya están probados (Fase 1).
- `AuthContext` es un módulo compartido con las Tandas 1-2 -- cualquier cambio a su `Estado` mantiene los nombres y el comportamiento de `"cargando"`/`"sin_sesion"`/`"autenticado"` intactos (los usan `(vecino)/*` y `app/_layout.tsx` ya construidos). El estado `"sin_membresia"` (Tanda 1) se **renombra** a `"devquad_sin_condominio"` -- antes era un callejón sin salida ("modo administrador no disponible todavía"), ahora es el primer paso real de un flujo. Todo archivo que lo usaba se actualiza en la Tarea 1.
- Push notifications sigue acotado a Alertas/vecino (Tanda 1) -- esta tanda no agrega ni consume notificaciones para devquad, no hace falta registrar el dispositivo en este flujo.
- Una pantalla de administración no asume el condominio activo -- lo lee de `useAuth().condominioActivo` (nuevo en la Tarea 1), nunca lo guarda por su cuenta.
- Mismo patrón de `.catch` en toda promesa y el mismo toolchain de testing ya establecido (`render()`/`fireEvent` siempre `await`, `jest.advanceTimersByTimeAsync`, tests de pantallas en `src/__tests__/app/...` nunca dentro de `src/app/`, `afterEach(async () => { await cleanup(); ... })`).
- Testing: TDD, suite completa `cd app_movil && npx jest --watchAll=false` antes de cada commit.

## Non-goals (fuera de esta tanda, a propósito)

- **"Mover miembro" entre condominios** (`MembresiaViewSet.mover`, equivalente a `MoverMiembroView` del panel web). Es una acción rara (reasignar a alguien a otro condominio), devquad la sigue haciendo desde el panel web mientras tanto.
- **Editar/borrar** una Torre o Unidad ya creada, o **borrar** un miembro. El panel web tampoco permite editar/borrar Torres/Unidades (`http_method_names = ["get", "post", ...]` en los ViewSets, sin `put`/`patch`/`delete`) -- esta tanda refleja exactamente lo que el backend ya permite, no agrega nada nuevo de ese lado.
- **Notificaciones push para devquad.** Fuera de alcance (ver Global Constraints).

## Review Focus

- Una cuenta devquad reabre la app con tokens guardados -- nunca asume que sigue "en" el mismo condominio que la vez anterior (D-07 implícito: confirmar siempre, mismo criterio que el hallazgo I1 de la Tanda 1) -- siempre vuelve a `devquad_sin_condominio` al reiniciar, nunca intenta recordar un condominio activo previo.
- Crear un miembro muestra usuario y contraseña temporal generados por el backend -- es la ÚNICA vez que esa contraseña es visible; si la pantalla los pierde (ej. un error después de la respuesta exitosa), devquad no tiene forma de recuperarlos sin ir al panel web.
- Crear una Unidad con una Torre de otro condominio -- el backend ya lo rechaza (`UnidadSerializer.validate`), la pantalla tiene que mostrar ESE mensaje real (vía `ErrorDeServidor.body`, Tarea 2 de la Tanda 2), no uno genérico.
- Elegir un condominio falla (sin red, timeout) -- no debe dejar a devquad en un estado intermedio raro (ni "cargando" para siempre, ni tokens corruptos); debe poder reintentar.
- Un error de validación con VARIOS campos inválidos a la vez (ej. crear un miembro sin rol y con un email ya usado) -- confirmar qué mensaje muestra la pantalla y que no sea confuso (el reviewer de la Tanda 2 ya marcó esto como Minor ahí -- acá se escribe al menos un test que documente el comportamiento real, para no repetir la misma ambigüedad sin registrar).

---

## Nota sobre endpoints consumidos (ya existen, no se tocan)

| Acción | Método + ruta | Shape relevante |
|---|---|---|
| Listar condominios | `GET /api/v1/devquad/condominios/` | lista de `{id, nombre, plan, puede_operar}` |
| Entrar a un condominio | `POST /api/v1/devquad/condominios/<pk>/entrar/` `{refresh}` | `{access, refresh, condominio: {id, nombre, plan, puede_operar}}` -- el refresh recibido se blacklistea, el devuelto es el nuevo activo |
| Mi condominio (ver) | `GET /api/v1/condominio/` | `CondominioEdicionOut` (ver abajo) |
| Mi condominio (editar) | `PATCH /api/v1/condominio/` | mismo shape, `partial=True` |
| Regenerar código de invitación | `POST /api/v1/condominio/regenerar-token/` | `{token_registro_residentes: string}` |
| Listar torres | `GET /api/v1/torres/` | lista de `{id, nombre}` |
| Crear torre | `POST /api/v1/torres/` `{nombre}` | `{id, nombre}` |
| Listar unidades | `GET /api/v1/unidades/` (paginado, 50/página) | `{count, next, previous, results: UnidadOut[]}` |
| Crear unidad | `POST /api/v1/unidades/` `{numero, calle?, torre?, alicuota?}` | `UnidadOut` |
| Listar miembros | `GET /api/v1/miembros/` (paginado, 50/página) | `{count, next, previous, results: MiembroOut[]}` |
| Crear miembro | `POST /api/v1/miembros/` `{nombre, apellido, email, rol, unidad?}` | `{id, username, password_temporal}` |

```ts
type CondominioEdicionOut = {
  nombre: string;
  etiqueta_organizacion: string;
  direccion: string;
  comuna: string;
  region: string;
  datos_transferencia: string;
  etiqueta_torre: string;
  etiqueta_unidad: string;
  genero_unidad: "f" | "m";
};

type UnidadOut = {
  id: number;
  numero: string;
  calle: string;
  torre: number | null;
  alicuota: string | null;
};

type MiembroOut = {
  id: number;
  nombre: string;
  rol: "residente" | "delegado";
  rol_display: string;
  unidad_numero: string | null;
  unidad_torre: string | null;
};
```

---

## File Structure

```
app_movil/src/
  auth/
    AuthContext.tsx       (modificar -- estado devquad_sin_condominio/devquad_con_condominio)
    AuthContext.test.tsx  (modificar -- renombrar tests de sin_membresia, agregar los de elegirCondominio)
  api/
    devquad.ts            (nuevo -- listarCondominiosDevquad, entrarCondominio)
    condominio.ts         (nuevo -- obtenerMiCondominio, actualizarMiCondominio, regenerarCodigoInvitacion)
    torres.ts              (nuevo -- listarTorres, crearTorre)
    unidades.ts            (nuevo -- listarUnidades, crearUnidad)
    miembros.ts            (nuevo -- listarMiembros, crearMiembro)
  app/
    elegir-condominio.tsx  (nuevo -- reemplaza sin-membresia.tsx)
    _layout.tsx            (modificar -- enruta devquad_sin_condominio/devquad_con_condominio)
    (admin)/
      _layout.tsx           (nuevo -- Drawer separado, D-07)
      condominio/index.tsx  (nuevo -- Mi condominio; landing del modo administrador)
      torres/index.tsx      (nuevo)
      unidades/index.tsx    (nuevo)
      miembros/index.tsx    (nuevo)
  __tests__/app/
    elegir-condominio.test.tsx
    (admin)/
      condominio/index.test.tsx
      torres/index.test.tsx
      unidades/index.test.tsx
      miembros/index.test.tsx

(se borra app/sin-membresia.tsx -- reemplazado por elegir-condominio.tsx)
```

---

### Task 1: `AuthContext` -- modo administrador (estado + elegir condominio)

**Files:**
- Modify: `app_movil/src/auth/AuthContext.tsx`
- Modify: `app_movil/src/auth/AuthContext.test.tsx`
- Create: `app_movil/src/api/devquad.ts`
- Create: `app_movil/src/api/devquad.test.ts`

**Interfaces:**
- Consumes: `apiFetch`, `guardarTokens`/`obtenerTokens` (ya existen).
- Produces:
  - `listarCondominiosDevquad(): Promise<{id: number, nombre: string, plan: string, puede_operar: boolean}[]>`, `entrarCondominio(id: number, refresh: string): Promise<{access: string, refresh: string, condominio: {id: number, nombre: string, plan: string, puede_operar: boolean}}>` en `api/devquad.ts`.
  - `Estado` pasa a `"cargando" | "sin_sesion" | "autenticado" | "devquad_sin_condominio" | "devquad_con_condominio"` (renombra `"sin_membresia"` → `"devquad_sin_condominio"`, agrega `"devquad_con_condominio"`).
  - `useAuth()` gana `condominioActivo: {id: number, nombre: string} | null` y dos funciones: `elegirCondominio(id: number): Promise<void>` (llama `entrarCondominio` con el refresh actual, guarda los tokens nuevos, pasa a `devquad_con_condominio`) y `volverAElegirCondominio(): void` (vuelve a `devquad_sin_condominio` sin tocar tokens -- para "cambiar de condominio" desde dentro del modo administrador).

- [ ] **Step 1: Escribir los tests de `api/devquad.ts` (fallan primero)**

```ts
jest.mock("./client");
import { listarCondominiosDevquad, entrarCondominio } from "./devquad";
import { apiFetch } from "./client";

test("listarCondominiosDevquad pide /api/v1/devquad/condominios/", async () => {
  (apiFetch as jest.Mock).mockResolvedValue([]);
  await listarCondominiosDevquad();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/devquad/condominios/");
});

test("entrarCondominio manda el refresh actual al endpoint correcto", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ access: "a", refresh: "r", condominio: { id: 1, nombre: "X" } });
  await entrarCondominio(1, "refresh-actual");
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/devquad/condominios/1/entrar/", {
    method: "POST",
    body: JSON.stringify({ refresh: "refresh-actual" }),
  });
});
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest src/api/devquad.test.ts --watchAll=false`

- [ ] **Step 3: Implementar `api/devquad.ts`**

- [ ] **Step 4: Correr, confirmar que pasan**

- [ ] **Step 5: Actualizar los tests de `AuthContext` que usaban `sin_membresia` (renombrar, fallan primero contra el código viejo)**

En `AuthContext.test.tsx`, los dos tests que hoy esperan `"sin_membresia"` (login de devquad, y restauración con 409) pasan a esperar `"devquad_sin_condominio"`. Son los mismos tests, mismo comportamiento -- solo el nombre del estado cambia.

- [ ] **Step 6: Correr, confirmar que fallan (todavía dice "sin_membresia" en el código)**

Run: `cd app_movil && npx jest src/auth/AuthContext.test.tsx --watchAll=false`
Expected: FAIL -- el estado real sigue siendo `"sin_membresia"`.

- [ ] **Step 7: Renombrar en `AuthContext.tsx`**

Cambiar el tipo `Estado` y las 3 ocurrencias de `setEstado("sin_membresia")` a `setEstado("devquad_sin_condominio")`.

- [ ] **Step 8: Correr, confirmar que pasan**

- [ ] **Step 9: Escribir los tests de `elegirCondominio`/`volverAElegirCondominio` (fallan primero)**

```tsx
test("elegirCondominio guarda los tokens nuevos y pasa a devquad_con_condominio", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue(null);
  jest.spyOn(storage, "guardarTokens").mockResolvedValue();
  jest.spyOn(authApi, "login").mockResolvedValue({ access: "a", refresh: "r", membresia: null });
  const guardarSpy = jest.spyOn(storage, "guardarTokens");
  jest.spyOn(devquadApi, "entrarCondominio").mockResolvedValue({
    access: "a2", refresh: "r2", condominio: { id: 5, nombre: "Empart", plan: "premium", puede_operar: true },
  });
  let auth: ReturnType<typeof useAuth>;
  function Capturador() { auth = useAuth(); return null; }
  await act(async () => { render(<AuthProvider><Capturador /></AuthProvider>); });
  await waitFor(() => expect(auth.estado).toBe("sin_sesion"));
  await act(() => auth!.iniciarSesion("devquad", "clave"));
  await waitFor(() => expect(auth.estado).toBe("devquad_sin_condominio"));
  await act(() => auth!.elegirCondominio(5));
  expect(guardarSpy).toHaveBeenCalledWith("a2", "r2");
  expect(auth!.estado).toBe("devquad_con_condominio");
  expect(auth!.condominioActivo).toEqual({ id: 5, nombre: "Empart" });
});

test("volverAElegirCondominio vuelve a devquad_sin_condominio sin tocar tokens", async () => {
  // (montar ya en devquad_con_condominio -- reusar el setup de arriba hasta elegirCondominio,
  // luego llamar auth.volverAElegirCondominio() y confirmar el estado + que borrarTokens NO se llamó)
});
```

(Importar `* as devquadApi from "../api/devquad"` al inicio del archivo de test.)

- [ ] **Step 10: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest src/auth/AuthContext.test.tsx --watchAll=false`

- [ ] **Step 11: Implementar `elegirCondominio`/`volverAElegirCondominio` y el campo `condominioActivo`**

- [ ] **Step 12: Correr, confirmar que pasan**

Run: `cd app_movil && npx jest src/auth/AuthContext.test.tsx --watchAll=false`
Expected: PASS

- [ ] **Step 13: Suite completa + commit**

Run: `cd app_movil && npx jest --watchAll=false`

```bash
git add app_movil/src/auth/AuthContext.tsx app_movil/src/auth/AuthContext.test.tsx app_movil/src/api/devquad.ts app_movil/src/api/devquad.test.ts
git commit -m "feat: AuthContext -- modo administrador (elegir condominio)"
git push
```

---

### Task 2: Pantalla "Elegir condominio"

**Files:**
- Create: `app_movil/src/app/elegir-condominio.tsx`
- Delete: `app_movil/src/app/sin-membresia.tsx`
- Modify: `app_movil/src/app/_layout.tsx` (el guard redirige a `/elegir-condominio` en vez de `/sin-membresia`, y a `/condominio` cuando `devquad_con_condominio`)
- Create: `app_movil/src/__tests__/app/elegir-condominio.test.tsx`

**Interfaces:**
- Consumes: `listarCondominiosDevquad` (Tarea 1), `useAuth().elegirCondominio` (Tarea 1).

- [ ] **Step 1: Escribir los tests de la pantalla (fallan primero)**

```tsx
jest.mock("@/auth/AuthContext", () => ({ useAuth: () => ({ elegirCondominio: jest.fn() }) }));
// (el mock de elegirCondominio se reemplaza por un jest.fn() capturable dentro de cada test via jest.spyOn sobre el módulo real -- NO mockear todo el módulo si el test necesita espiar la llamada. Ver nota abajo.)
```

Nota para quien implemente: a diferencia de otras pantallas, ACÁ el test sí necesita comprobar que `elegirCondominio` se llamó con el id correcto -- mockear el módulo completo (como en los tests de rol de Avisos/Directorio) no permite eso. Usar en cambio un wrapper real: renderizar `<AuthProviderDeMentira>` propio en el test (un componente mínimo que provee el mismo Context con un `elegirCondominio: jest.fn()` capturable), o mockear `@/api/devquad` y `@/auth/AuthContext` parcialmente con `jest.spyOn` sobre sus exports reales en vez de `jest.mock` de módulo completo. Cualquiera de los dos cumple, elegir el más simple de escribir.

```tsx
import { render, fireEvent, screen } from "@testing-library/react-native";
import ElegirCondominioScreen from "@/app/elegir-condominio";
import * as devquadApi from "@/api/devquad";
import * as authContext from "@/auth/AuthContext";
import { ErrorDeRed } from "@/api/client";

afterEach(() => jest.restoreAllMocks());

test("lista los condominios y al tocar uno llama a elegirCondominio", async () => {
  jest.spyOn(devquadApi, "listarCondominiosDevquad").mockResolvedValue([
    { id: 5, nombre: "Empart", plan: "premium", puede_operar: true },
  ]);
  const elegirSpy = jest.fn().mockResolvedValue(undefined);
  jest.spyOn(authContext, "useAuth").mockReturnValue({ elegirCondominio: elegirSpy } as any);
  await render(<ElegirCondominioScreen />);
  await fireEvent.press(await screen.findByText("Empart"));
  expect(elegirSpy).toHaveBeenCalledWith(5);
});

test("si falla listar los condominios, muestra un error", async () => {
  jest.spyOn(devquadApi, "listarCondominiosDevquad").mockRejectedValue(new ErrorDeRed("sin red"));
  jest.spyOn(authContext, "useAuth").mockReturnValue({ elegirCondominio: jest.fn() } as any);
  await render(<ElegirCondominioScreen />);
  await screen.findByText(/no se pudieron cargar los condominios/i);
});

test("si elegirCondominio falla, muestra un error y deja reintentar (no queda en un estado intermedio raro)", async () => {
  jest.spyOn(devquadApi, "listarCondominiosDevquad").mockResolvedValue([
    { id: 5, nombre: "Empart", plan: "premium", puede_operar: true },
  ]);
  const elegirSpy = jest.fn().mockRejectedValue(new ErrorDeRed("sin red"));
  jest.spyOn(authContext, "useAuth").mockReturnValue({ elegirCondominio: elegirSpy } as any);
  await render(<ElegirCondominioScreen />);
  await fireEvent.press(await screen.findByText("Empart"));
  await screen.findByText(/no se pudo entrar a ese condominio/i);
  await fireEvent.press(screen.getByText("Empart"));
  expect(elegirSpy).toHaveBeenCalledTimes(2);
});
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest "src/__tests__/app/elegir-condominio" --watchAll=false`

- [ ] **Step 3: Implementar la pantalla**

Lista simple (`FlatList`, nombre + plan), cada fila llama `elegirCondominio(item.id)` envuelta en try/catch para el error de la Tarea. Nada de doble-toque aquí hace falta proteger con el mismo rigor que un botón de pánico/aviso -- entrar dos veces al mismo condominio no duplica nada del lado del servidor (`DevquadEntrarCondominioApiView` simplemente blacklistea el refresh anterior y emite uno nuevo) -- pero si ya hay una elección en curso, ignorar toques nuevos evita 2 requests superpuestas pisándose los tokens guardados.

- [ ] **Step 4: Correr, confirmar que pasan**

- [ ] **Step 5: Borrar `sin-membresia.tsx`, actualizar el guard de `_layout.tsx`**

En `GuardDeRutas`, reemplazar las referencias a `"sin_membresia"`/`"/sin-membresia"` por `"devquad_sin_condominio"`/`"/elegir-condominio"`; agregar que `"devquad_con_condominio"` redirige a `"/condominio"` (la pantalla de Mi condominio, Tarea 4 -- que hace de landing del modo administrador) si no está ya en una ruta de `(admin)`.

**Ruling de diseño ya verificado (no a criterio de quien implemente):** `(admin)/` NO tiene un `index.tsx` propio. Se probó directo (`npx expo start --web` con un `(admin)/index.tsx` de prueba) y Expo Router resuelve `(admin)/index.tsx` y `(vecino)/index.tsx` a la MISMA ruta `/` sin ningún error ni warning -- uno de los dos gana en silencio y el otro queda inalcanzable. Por eso el guard redirige directo a `/condominio` (`(admin)/condominio/index.tsx`, que vive un nivel más adentro y no colisiona con nada), nunca a `/` ni a `/(admin)`.

- [ ] **Step 6: Suite completa + verificación manual + commit**

Run: `cd app_movil && npx jest --watchAll=false`

Run: `cd app_movil && npx expo start --web` (manual, `/elegir-condominio` sin error, detener el servidor).

```bash
git add app_movil/src/app/elegir-condominio.tsx app_movil/src/app/sin-membresia.tsx app_movil/src/app/_layout.tsx app_movil/src/__tests__/app/elegir-condominio.test.tsx
git commit -m "feat: pantalla Elegir condominio (reemplaza sin-membresia)"
git push
```

---

### Task 3: Layout del modo administrador

**Files:**
- Create: `app_movil/src/app/(admin)/_layout.tsx`

**Interfaces:**
- Consumes: `useAuth().condominioActivo`, `useAuth().volverAElegirCondominio` (Tarea 1).

- [ ] **Step 1: Implementar (sin test automático -- composición de navegación, mismo criterio que `(vecino)/_layout.tsx` en la Tanda 1)**

`(admin)/_layout.tsx`: un Drawer separado (D-07, no reusa el de `(vecino)/`), con el nombre del `condominioActivo` en el header, y una entrada "Cambiar condominio" que llama `volverAElegirCondominio()`. Rutas: `condominio/index`, `torres/index`, `unidades/index`, `miembros/index`. No hay ningún `index.tsx` en la raíz de `(admin)/` (ver el Ruling ya verificado de la Tarea 2 -- colisionaría con `(vecino)/index.tsx` en la ruta `/`); "Mi condominio" (`condominio/index`, Tarea 4) hace de landing, y el guard de `_layout.tsx` ya redirige ahí directo.

- [ ] **Step 2: Suite completa + verificación manual + commit**

Run: `cd app_movil && npx jest --watchAll=false`

Run: `cd app_movil && npx expo start --web` (manual, confirmar que no rompe nada ya existente, detener el servidor).

```bash
git add app_movil/src/app/\(admin\)
git commit -m "feat: layout del modo administrador (D-07, separado del drawer de vecino)"
git push
```

---

### Task 4: Mi condominio -- ver/editar + regenerar código de invitación

**Files:**
- Create: `app_movil/src/api/condominio.ts`
- Create: `app_movil/src/app/(admin)/condominio/index.tsx`
- Create: `app_movil/src/__tests__/app/(admin)/condominio/index.test.tsx`

**Interfaces:**
- Produces: `obtenerMiCondominio(): Promise<CondominioEdicionOut>`, `actualizarMiCondominio(datos: Partial<CondominioEdicionOut>): Promise<CondominioEdicionOut>`, `regenerarCodigoInvitacion(): Promise<{token_registro_residentes: string}>`.

- [ ] **Step 1: Escribir los tests de `api/condominio.ts` (fallan primero)**

```ts
jest.mock("./client");
import { obtenerMiCondominio, actualizarMiCondominio, regenerarCodigoInvitacion } from "./condominio";
import { apiFetch } from "./client";

test("obtenerMiCondominio pide /api/v1/condominio/", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({});
  await obtenerMiCondominio();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/condominio/");
});

test("actualizarMiCondominio hace PATCH", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({});
  await actualizarMiCondominio({ nombre: "Nuevo nombre" });
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/condominio/", {
    method: "PATCH",
    body: JSON.stringify({ nombre: "Nuevo nombre" }),
  });
});

test("regenerarCodigoInvitacion pega al endpoint correcto", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ token_registro_residentes: "abc" });
  await regenerarCodigoInvitacion();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/condominio/regenerar-token/", { method: "POST" });
});
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest src/api/condominio.test.ts --watchAll=false`

- [ ] **Step 3: Implementar `api/condominio.ts`**

- [ ] **Step 4: Correr, confirmar que pasan**

- [ ] **Step 5: Escribir los tests de la pantalla (fallan primero)**

```tsx
import { render, fireEvent, screen } from "@testing-library/react-native";
import PantallaMiCondominio from "@/app/(admin)/condominio/index";
import * as condominioApi from "@/api/condominio";
import { ErrorDeRed } from "@/api/client";

afterEach(() => jest.restoreAllMocks());

test("al montar, carga y pre-llena el formulario", async () => {
  jest.spyOn(condominioApi, "obtenerMiCondominio").mockResolvedValue({
    nombre: "Empart", etiqueta_organizacion: "condominio", direccion: "Calle 1", comuna: "Viña del Mar",
    region: "Valparaíso", datos_transferencia: "", etiqueta_torre: "Torre", etiqueta_unidad: "Departamento",
    genero_unidad: "m",
  });
  await render(<PantallaMiCondominio />);
  await screen.findByDisplayValue("Empart");
});

test("si falla la carga, no muestra el formulario (mismo criterio que Mi perfil, Tanda 2 -- guardar sobre un formulario vacío borraría datos reales)", async () => {
  jest.spyOn(condominioApi, "obtenerMiCondominio").mockRejectedValue(new ErrorDeRed("sin red"));
  await render(<PantallaMiCondominio />);
  await screen.findByText(/no se pudo cargar/i);
  expect(screen.queryByText(/guardar/i)).toBeNull();
});

test("al tocar Regenerar código, pide confirmación antes de invalidar el link anterior", async () => {
  jest.spyOn(condominioApi, "obtenerMiCondominio").mockResolvedValue({
    nombre: "Empart", etiqueta_organizacion: "condominio", direccion: "", comuna: "", region: "",
    datos_transferencia: "", etiqueta_torre: "Torre", etiqueta_unidad: "Departamento", genero_unidad: "m",
  });
  const regenerarSpy = jest.spyOn(condominioApi, "regenerarCodigoInvitacion").mockResolvedValue({
    token_registro_residentes: "nuevo",
  });
  await render(<PantallaMiCondominio />);
  await screen.findByDisplayValue("Empart");
  await fireEvent.press(screen.getByText(/regenerar código/i));
  // confirmar vía un diálogo (Alert.alert con 2 botones) antes de llamar -- ver Step 7
  expect(regenerarSpy).not.toHaveBeenCalled();
});
```

Nota: el test de confirmación es deliberadamente mínimo (solo confirma que NO se llama antes de confirmar) -- `Alert.alert` de React Native no se puede "tocar" fácilmente desde un test sin mockear `Alert.alert` entero; mockearlo y capturar su callback de confirmación para invocarlo a mano es válido si quien implementa prefiere una prueba más completa.

- [ ] **Step 6: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest "src/__tests__/app/\(admin\)/condominio" --watchAll=false`

- [ ] **Step 7: Implementar la pantalla**

Mismo patrón que Mi Perfil (Tanda 2): si falla la carga, no se muestra el formulario, solo error + "Reintentar". "Regenerar código" usa `Alert.alert("¿Regenerar el código de invitación?", "El link anterior deja de funcionar.", [{text: "Cancelar"}, {text: "Regenerar", onPress: ...}])` antes de llamar al endpoint -- invalidar el link vigente sin avisar sería destructivo para cualquiera que lo tenga compartido sin usar todavía.

- [ ] **Step 8: Correr, confirmar que pasan**

- [ ] **Step 9: Agregar al Drawer (ya hecho en la Tarea 3 si se nombró `condominio/index` ahí -- confirmar)**

- [ ] **Step 10: Suite completa + verificación manual + commit**

Run: `cd app_movil && npx jest --watchAll=false`

Run: `cd app_movil && npx expo start --web` (manual, detener el servidor).

```bash
git add app_movil/src/api/condominio.ts app_movil/src/api/condominio.test.ts app_movil/src/app/\(admin\)/condominio app_movil/src/__tests__/app/\(admin\)/condominio
git commit -m "feat: Mi condominio -- ver/editar y regenerar codigo de invitacion"
git push
```

---

### Task 5: Torres -- listar y crear

**Files:**
- Create: `app_movil/src/api/torres.ts`
- Create: `app_movil/src/app/(admin)/torres/index.tsx`
- Create: `app_movil/src/__tests__/app/(admin)/torres/index.test.tsx`

**Interfaces:**
- Produces: `listarTorres(): Promise<{id: number, nombre: string}[]>`, `crearTorre(nombre: string): Promise<{id: number, nombre: string}>`.

- [ ] **Step 1: Escribir los tests de `api/torres.ts` (fallan primero)**

```ts
jest.mock("./client");
import { listarTorres, crearTorre } from "./torres";
import { apiFetch } from "./client";

test("listarTorres pide /api/v1/torres/", async () => {
  (apiFetch as jest.Mock).mockResolvedValue([]);
  await listarTorres();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/torres/");
});

test("crearTorre manda el nombre", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ id: 1, nombre: "A" });
  await crearTorre("A");
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/torres/", { method: "POST", body: JSON.stringify({ nombre: "A" }) });
});
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest src/api/torres.test.ts --watchAll=false`

- [ ] **Step 3: Implementar `api/torres.ts`**

- [ ] **Step 4: Correr, confirmar que pasan**

- [ ] **Step 5: Escribir los tests de la pantalla (fallan primero)**

```tsx
import { render, fireEvent, screen } from "@testing-library/react-native";
import TorresScreen from "@/app/(admin)/torres/index";
import * as torresApi from "@/api/torres";
import { ErrorDeRed, ErrorDeServidor } from "@/api/client";

afterEach(() => jest.restoreAllMocks());

test("lista las torres y permite crear una nueva", async () => {
  jest.spyOn(torresApi, "listarTorres").mockResolvedValue([{ id: 1, nombre: "A" }]);
  const crearSpy = jest.spyOn(torresApi, "crearTorre").mockResolvedValue({ id: 2, nombre: "B" });
  await render(<TorresScreen />);
  await screen.findByText("A");
  await fireEvent.changeText(screen.getByPlaceholderText(/nombre/i), "B");
  await fireEvent.press(screen.getByText(/agregar/i));
  expect(crearSpy).toHaveBeenCalledWith("B");
  await screen.findByText("B");
});

test("si falla crear (ej. nombre vacío), muestra el mensaje real del backend", async () => {
  // Torre NO tiene restricción de nombre único (core/models.py) -- el único
  // error de validación real que TorreSerializer puede devolver es un
  // nombre vacío. Texto exacto confirmado contra el backend real.
  jest.spyOn(torresApi, "listarTorres").mockResolvedValue([]);
  jest.spyOn(torresApi, "crearTorre").mockRejectedValue(
    new ErrorDeServidor(400, { nombre: ["Este campo no puede estar en blanco."] })
  );
  await render(<TorresScreen />);
  await fireEvent.press(await screen.findByText(/agregar/i));
  await screen.findByText(/este campo no puede estar en blanco/i);
});

test("si falla listar, muestra un error", async () => {
  jest.spyOn(torresApi, "listarTorres").mockRejectedValue(new ErrorDeRed("sin red"));
  await render(<TorresScreen />);
  await screen.findByText(/no se pudieron cargar las torres/i);
});
```

- [ ] **Step 6: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest "src/__tests__/app/\(admin\)/torres" --watchAll=false`

- [ ] **Step 7: Implementar la pantalla**

Reusar `primerMensajeDeError` de Mi Perfil (Tanda 2) -- es exactamente la misma necesidad (mostrar el primer mensaje real de un `ErrorDeServidor.body`). Moverla a un módulo compartido (`src/api/erroresFormulario.ts` o similar) en vez de copiarla, ya que esta es la segunda pantalla que la necesita.

- [ ] **Step 8: Correr, confirmar que pasan (y que Mi Perfil y Mi Condominio siguen pasando tras mover la función compartida)**

Run: `cd app_movil && npx jest --watchAll=false`

- [ ] **Step 9: Agregar al Drawer (ya hecho en la Tarea 3 -- confirmar)**

- [ ] **Step 10: Verificación manual + commit**

Run: `cd app_movil && npx expo start --web` (manual, detener el servidor).

```bash
git add app_movil/src/api/torres.ts app_movil/src/api/torres.test.ts app_movil/src/app/\(admin\)/torres app_movil/src/__tests__/app/\(admin\)/torres app_movil/src/api/erroresFormulario.ts app_movil/src/app/\(vecino\)/perfil/index.tsx app_movil/src/app/\(admin\)/condominio/index.tsx
git commit -m "feat: torres -- listar y crear; comparte el parser de errores de formulario con Mi perfil/Mi condominio"
git push
```

---

### Task 6: Unidades -- listar y crear

**Files:**
- Create: `app_movil/src/api/unidades.ts`
- Create: `app_movil/src/app/(admin)/unidades/index.tsx`
- Create: `app_movil/src/__tests__/app/(admin)/unidades/index.test.tsx`

**Interfaces:**
- Consumes: `listarTorres` (Tarea 5, para el selector de torre al crear).
- Produces: `listarUnidades(): Promise<UnidadOut[]>` (sin paginar del lado del cliente en esta tanda -- la primera página basta para la lista; paginar la UI queda a criterio de quien lo construya, ver más abajo), `crearUnidad(payload: {numero: string, calle?: string, torre?: number, alicuota?: string}): Promise<UnidadOut>`.

- [ ] **Step 1: Escribir los tests de `api/unidades.ts` (fallan primero)**

```ts
jest.mock("./client");
import { listarUnidades, crearUnidad } from "./unidades";
import { apiFetch } from "./client";

test("listarUnidades pide /api/v1/unidades/ y devuelve results", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ count: 1, next: null, previous: null, results: [{ id: 1, numero: "101" }] });
  const resultado = await listarUnidades();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/unidades/");
  expect(resultado).toEqual([{ id: 1, numero: "101" }]);
});

test("crearUnidad manda el payload dado", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ id: 2, numero: "102" });
  await crearUnidad({ numero: "102", torre: 1 });
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/unidades/", {
    method: "POST",
    body: JSON.stringify({ numero: "102", torre: 1 }),
  });
});
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest src/api/unidades.test.ts --watchAll=false`

- [ ] **Step 3: Implementar `api/unidades.ts`**

`listarUnidades()` llama `apiFetch<{results: UnidadOut[]}>("/api/v1/unidades/")` y devuelve `.results` -- el shape paginado de DRF (`PageNumberPagination`) envuelve la lista real.

- [ ] **Step 4: Correr, confirmar que pasan**

- [ ] **Step 5: Escribir los tests de la pantalla (fallan primero)**

```tsx
import { render, fireEvent, screen } from "@testing-library/react-native";
import UnidadesScreen from "@/app/(admin)/unidades/index";
import * as unidadesApi from "@/api/unidades";
import * as torresApi from "@/api/torres";
import { ErrorDeServidor } from "@/api/client";

afterEach(() => jest.restoreAllMocks());

test("lista las unidades y permite crear una nueva sin torre", async () => {
  jest.spyOn(torresApi, "listarTorres").mockResolvedValue([]);
  jest.spyOn(unidadesApi, "listarUnidades").mockResolvedValue([{ id: 1, numero: "101", calle: "", torre: null, alicuota: null }]);
  const crearSpy = jest.spyOn(unidadesApi, "crearUnidad").mockResolvedValue({ id: 2, numero: "102", calle: "", torre: null, alicuota: null });
  await render(<UnidadesScreen />);
  await screen.findByText("101");
  await fireEvent.changeText(screen.getByPlaceholderText(/número/i), "102");
  await fireEvent.press(screen.getByText(/agregar/i));
  expect(crearSpy).toHaveBeenCalledWith({ numero: "102" });
});

test("si la torre elegida no pertenece al condominio, muestra el mensaje real del backend", async () => {
  // Texto exacto confirmado contra el backend real (UnidadSerializer.validate,
  // core/serializers.py) -- no es un mensaje inventado para el test.
  jest.spyOn(torresApi, "listarTorres").mockResolvedValue([{ id: 9, nombre: "Z" }]);
  jest.spyOn(unidadesApi, "listarUnidades").mockResolvedValue([]);
  jest.spyOn(unidadesApi, "crearUnidad").mockRejectedValue(
    new ErrorDeServidor(400, { torre: ["Esa torre pertenece a otro condominio."] })
  );
  await render(<UnidadesScreen />);
  await fireEvent.changeText(await screen.findByPlaceholderText(/número/i), "1");
  await fireEvent.press(screen.getByText(/agregar/i));
  await screen.findByText(/esa torre pertenece a otro condominio/i);
});
```

- [ ] **Step 6: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest "src/__tests__/app/\(admin\)/unidades" --watchAll=false`

- [ ] **Step 7: Implementar la pantalla**

El selector de torre es opcional (reusa el patrón de `SelectorTipoAlerta` de la Tanda 1 -- un control chico que despliega la lista de torres, o un simple `Picker`, a criterio); sin torre seleccionada, el payload de `crearUnidad` no incluye la clave `torre` en absoluto (no manda `torre: null`, que el backend podría interpretar distinto a "no mandado" -- confirmar contra `UnidadSerializer` si alcanza con omitir la clave).

- [ ] **Step 8: Correr, confirmar que pasan**

- [ ] **Step 9: Verificación manual + commit**

Run: `cd app_movil && npx jest --watchAll=false`

Run: `cd app_movil && npx expo start --web` (manual, detener el servidor).

```bash
git add app_movil/src/api/unidades.ts app_movil/src/api/unidades.test.ts app_movil/src/app/\(admin\)/unidades app_movil/src/__tests__/app/\(admin\)/unidades
git commit -m "feat: unidades -- listar y crear"
git push
```

---

### Task 7: Miembros -- listar y crear

**Files:**
- Create: `app_movil/src/api/miembros.ts`
- Create: `app_movil/src/app/(admin)/miembros/index.tsx`
- Create: `app_movil/src/__tests__/app/(admin)/miembros/index.test.tsx`

**Interfaces:**
- Consumes: `listarUnidades` (Tarea 6, para el selector de unidad al crear).
- Produces: `listarMiembros(): Promise<MiembroOut[]>` (misma forma paginada que Unidades -- devuelve `.results`), `crearMiembro(payload: {nombre: string, apellido: string, email: string, rol: "residente" | "delegado", unidad?: number}): Promise<{id: number, username: string, password_temporal: string}>`.

- [ ] **Step 1: Escribir los tests de `api/miembros.ts` (fallan primero)**

```ts
jest.mock("./client");
import { listarMiembros, crearMiembro } from "./miembros";
import { apiFetch } from "./client";

test("listarMiembros pide /api/v1/miembros/ y devuelve results", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ count: 1, next: null, previous: null, results: [{ id: 1, nombre: "Ana" }] });
  const resultado = await listarMiembros();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/miembros/");
  expect(resultado).toEqual([{ id: 1, nombre: "Ana" }]);
});

test("crearMiembro manda el payload dado", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ id: 2, username: "ana123", password_temporal: "xYz789" });
  const resultado = await crearMiembro({ nombre: "Ana", apellido: "Pérez", email: "a@test.cl", rol: "residente", unidad: 1 });
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/miembros/", {
    method: "POST",
    body: JSON.stringify({ nombre: "Ana", apellido: "Pérez", email: "a@test.cl", rol: "residente", unidad: 1 }),
  });
  expect(resultado.password_temporal).toBe("xYz789");
});
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest src/api/miembros.test.ts --watchAll=false`

- [ ] **Step 3: Implementar `api/miembros.ts`**

- [ ] **Step 4: Correr, confirmar que pasan**

- [ ] **Step 5: Escribir los tests de la pantalla (fallan primero)**

```tsx
import { render, fireEvent, screen } from "@testing-library/react-native";
import MiembrosScreen from "@/app/(admin)/miembros/index";
import * as miembrosApi from "@/api/miembros";
import * as unidadesApi from "@/api/unidades";

afterEach(() => jest.restoreAllMocks());

test("al crear un miembro, muestra el usuario y la contraseña temporal generados", async () => {
  jest.spyOn(unidadesApi, "listarUnidades").mockResolvedValue([]);
  jest.spyOn(miembrosApi, "listarMiembros").mockResolvedValue([]);
  jest.spyOn(miembrosApi, "crearMiembro").mockResolvedValue({ id: 1, username: "ana123", password_temporal: "xYz789" });
  await render(<MiembrosScreen />);
  await fireEvent.changeText(await screen.findByPlaceholderText(/nombre/i), "Ana");
  await fireEvent.changeText(screen.getByPlaceholderText(/apellido/i), "Pérez");
  await fireEvent.changeText(screen.getByPlaceholderText(/correo/i), "a@test.cl");
  await fireEvent.press(screen.getByText(/crear miembro/i));
  await screen.findByText("ana123");
  await screen.findByText("xYz789");
});

test("el usuario y la contraseña generados siguen visibles aunque la lista se recargue después", async () => {
  // Hallazgo del Review Focus: la única vez que la contraseña es visible
  // -- no puede perderse si, por ejemplo, volver a listar falla o tarda.
  jest.spyOn(unidadesApi, "listarUnidades").mockResolvedValue([]);
  jest.spyOn(miembrosApi, "listarMiembros").mockResolvedValue([]);
  jest.spyOn(miembrosApi, "crearMiembro").mockResolvedValue({ id: 1, username: "ana123", password_temporal: "xYz789" });
  await render(<MiembrosScreen />);
  await fireEvent.changeText(await screen.findByPlaceholderText(/nombre/i), "Ana");
  await fireEvent.changeText(screen.getByPlaceholderText(/apellido/i), "Pérez");
  await fireEvent.changeText(screen.getByPlaceholderText(/correo/i), "a@test.cl");
  await fireEvent.press(screen.getByText(/crear miembro/i));
  await screen.findByText("xYz789");
  expect(screen.getByText("xYz789")).toBeTruthy();
});
```

- [ ] **Step 6: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest "src/__tests__/app/\(admin\)/miembros" --watchAll=false`

- [ ] **Step 7: Implementar la pantalla**

El resultado de `crearMiembro` (usuario + contraseña) se guarda en un estado propio, separado de la lista (ej. `credencialesNuevas`), y se muestra en un bloque fijo que no depende de que la lista se vuelva a cargar con éxito. Formulario: nombre, apellido, correo, selector de rol (residente/delegado), selector de unidad (opcional, reusando el mismo criterio que el selector de torre de la Tarea 6).

- [ ] **Step 8: Correr, confirmar que pasan**

- [ ] **Step 9: Suite completa + verificación manual + commit**

Run: `cd app_movil && npx jest --watchAll=false`

Run: `cd app_movil && npx expo start --web` (manual, confirmar TODAS las rutas de la app -- vecino y administrador -- antes de cerrar la tanda, detener el servidor).

```bash
git add app_movil/src/api/miembros.ts app_movil/src/api/miembros.test.ts app_movil/src/app/\(admin\)/miembros app_movil/src/__tests__/app/\(admin\)/miembros
git commit -m "feat: miembros -- listar y crear (usuario + contraseña temporal)"
git push
```

---

## Self-Review (hecho al escribir este plan)

**Cobertura del spec:** D-07 completo -- elegir condominio (Tareas 1-2), separación de navegación (Tarea 3), miembros/torres/unidades (Tareas 5-7), Mi condominio (Tarea 4).

**Review Focus:** los 5 puntos tienen tarea y test propios -- devquad siempre vuelve a elegir condominio al reabrir (Tarea 1, mismo criterio que I1 de la Tanda 1), contraseña temporal no se pierde (Tarea 7), mensaje real de validación de Unidad/Torre (Tareas 5-6, vía `ErrorDeServidor.body`), reintentar si falla elegir condominio (Tarea 2), un test que documenta el comportamiento real ante varios campos inválidos (ya cubierto indirectamente por los tests de un-solo-campo de las Tareas 5-6 -- si quien implementa encuentra que el comportamiento multi-campo es confuso, lo registra como hallazgo, no lo arregla a mitad de tarea).

**Consistencia de tipos:** `CondominioEdicionOut`/`UnidadOut`/`MiembroOut` se fijan una sola vez en la tabla de endpoints y se reusan tal cual. La función compartida de parseo de errores (`primerMensajeDeError`, movida en la Tarea 5) tiene la misma firma que ya usa Mi Perfil desde la Tanda 2 -- no se le cambia el comportamiento, solo la ubicación.

**Proporción:** 7 tareas -- 2 de infraestructura (auth + elegir condominio), 1 de navegación, 4 pantallas de gestión del mismo tamaño que las ya construidas en la Tanda 2.

## Qué queda a criterio de quien lo construya

- Diseño exacto del selector de torre/unidad (un control desplegable propio como `SelectorTipoAlerta`, o un `Picker` nativo) -- el plan fija que debe ser opcional y mandar el payload sin la clave si no se eligió nada, no el widget exacto.
- Si "Unidades" pagina de verdad en la UI (botón "cargar más") o solo muestra la primera página de 50 -- para un condominio como Empart (352 unidades) esto importa para el uso real, pero el plan no lo exige explícitamente; documentarlo como hallazgo si se deja solo la primera página.
- Mensaje y diseño exacto del diálogo de confirmación de "Regenerar código".
- Tanda 4 (pagos/foto/modo silencioso) de la Fase 2, y la Fase 3 (panel institucional), quedan para planes aparte, después de esta.

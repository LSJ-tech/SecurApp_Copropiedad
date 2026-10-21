# App móvil de Mi Barrio+ -- Tanda 1: Núcleo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir la primera tanda de la app móvil de Mi Barrio+ ("Núcleo", según el propio documento de diseño): login, el botón de pánico completo con sus 4 mejoras, recepción de push, y ver alertas activas/historial con "visto por". Al terminar, un residente puede instalar la app (o abrirla en el navegador vía Expo for Web), iniciar sesión, mandar una alerta real y verla reflejada en el backend ya existente -- software completo y probable de punta a punta, aunque solo cubra una parte del alcance total de la Fase 2.

**Architecture:** Proyecto Expo nuevo en `app_movil/` (TypeScript, Expo Router para la navegación por archivos, compatible nativo con Expo for Web). Server state mínimo: no se agrega una librería de cache de red -- cada pantalla llama directo al cliente API y guarda el resultado en estado local de React, mismo nivel de complejidad que lo que el backend ya expone. Autenticación por JWT (access + refresh de SimpleJWT, ya construidos en la Fase 1), guardados en almacenamiento seguro cross-platform (`expo-secure-store` en nativo, `localStorage` en Expo for Web, misma interfaz). Un refresco automático de token ante un 401 vive en un único cliente HTTP (`src/api/client.ts`), para que ninguna pantalla tenga que manejarlo a mano.

**Tech Stack:** Expo SDK (plantilla por defecto de `create-expo-app`, con Expo Router ya incluido), TypeScript, React Native, `expo-secure-store`, `expo-location`, `expo-notifications`, `@react-native-async-storage/async-storage`, `@react-navigation/drawer` (vía `expo-router/drawer`). Testing: `jest-expo` + `@testing-library/react-native`.

**Spec:** `docs/superpowers/specs/2026-10-19-app-movil-mi-barrio-design.md`

## Global Constraints

- Consume la API REST de la Fase 1 **tal cual** (`/api/v1/...`, JWT) -- este plan no modifica nada de Django/DRF. Todos los endpoints que se usan ya existen y ya están probados del lado del backend.
- Multiplataforma real: todo componente de UI se escribe para correr igual en iOS, Android y Expo for Web -- no se usa ninguna API nativa sin verificar que tiene (o no necesita) equivalente web (`expo-secure-store` es el caso que sí lo necesita, ver Tarea 2).
- Push notifications **acotado a celular** (iOS/Android) -- la salida Web de Expo for Web no registra dispositivo ni recibe push (D-xx de Constraints del spec). El registro de push (Tarea 6) debe no-operar en Web, no intentarlo y fallar.
- Reintento automático (D-04 #2) es "mientras la app sigue viva" -- una cola en memoria/AsyncStorage con reintento en foreground/background in-process. Ninguna tarea de este plan agrega background fetch nativo, config plugins, ni módulos nativos custom -- eso quedaría fuera de Expo managed workflow, explícitamente fuera de esta fase.
- El push a los vecinos ya sale de inmediato al crear la alerta del lado del backend, sin esperar la ventana de cancelar -- ninguna tarea de este plan debe introducir una espera artificial antes de mandar el POST de creación.
- Paleta de marca exacta (de `core/static/core/brand.css`, única fuente de verdad): `primary #102D46`, `primaryDark #284E6B`, `primaryDarker #0A1B2A`, `secondary #708090`, `accent #0D9488`, `slate #5B7A8C`.
- D-02: la confirmación del botón de pánico es un press-and-hold de **2000ms exactos**; soltar antes no dispara nada (se cancela solo, sin diálogo).
- D-03: el botón grande manda siempre `tipo="otro"` por defecto; el selector de tipo específico es un control aparte, nunca bloquea ni se interpone en el camino rápido.
- Fuera de alcance de este plan (quedan para tandas/fases posteriores, no se construye nada de esto acá): avisos, directorio, mi perfil, invitar/compartir (Tanda 2 de la app); modo administrador/devquad (Tanda 3, D-07); pagos, foto en alertas, modo silencioso (Non-goals del documento de diseño / Tanda 4).
- Testing: cada paso de código entra con su test en rojo primero (TDD). Suite completa del proyecto Expo: `cd app_movil && npx jest --watchAll=false`, corre en segundos (sin red real, todo mockeado) -- se corre completa antes de cada commit, no hace falta background.

## Review Focus

- **Ambos tokens (access y refresh) ya vencieron.** La app debe mandar limpiamente a la pantalla de login (borrando lo que quedó guardado), no quedar en un ciclo de reintentos silenciosos ni mostrar una pantalla en blanco. Cubierto en la Tarea 2 (cliente API) y la Tarea 3 (`AuthContext`).
- **El residente niega el permiso de ubicación al mandar una alerta.** D-04 #1 dice "automático", pero negar el permiso no puede bloquear ni demorar el envío del botón de pánico -- la alerta se manda igual, sin `latitud`/`longitud`. Cubierto en la Tarea 5.
- **El residente niega el permiso de notificaciones push.** No debe bloquear el resto de la app ni reintentarse en loop -- simplemente esa cuenta no recibe push, sin romper nada más. Cubierto en la Tarea 6.
- **Dos alertas quedan encoladas offline y la señal vuelve.** Deben reintentarse en el orden en que se crearon y ninguna debe duplicarse si ya había salido antes de perder la referencia en memoria (ej. recarga de la app). Cubierto en la Tarea 5.
- **Una cuenta devquad (sin Membresia) inicia sesión.** `MembresiaSerializer`/`/auth/login/` devuelven `membresia: null` para esas cuentas (confirmado en el backend) -- esta tanda no construye modo administrador (Tanda 3), así que la app no debe crashear ni quedar en blanco: debe mostrar un mensaje claro de que el modo administrador todavía no está disponible en esta versión. Cubierto en la Tarea 3.

---

## Nota sobre endpoints consumidos (ya existen, no se tocan)

| Acción | Método + ruta | Shape relevante de la respuesta |
|---|---|---|
| Login | `POST /api/v1/auth/login/` `{username, password}` | `{access, refresh, membresia: MembresiaOut \| null}` |
| Refrescar token | `POST /api/v1/auth/refresh/` `{refresh}` | `{access}` |
| Cerrar sesión | `POST /api/v1/auth/logout/` `{refresh}` | 205, sin cuerpo |
| Perfil propio | `GET /api/v1/auth/me/` | `MembresiaOut` (409 si no tiene Membresia) |
| Registrar push | `POST /api/v1/dispositivos/` `{token, plataforma: "ios"\|"android"}` | el dispositivo creado/actualizado |
| Listar alertas | `GET /api/v1/alertas/?estado=activa\|recientes\|resuelta\|falsa_alarma` (sin filtro = todas) | lista de `AlertaOut` |
| Crear alerta | `POST /api/v1/alertas/` `{tipo, mensaje?, latitud?, longitud?}` | `AlertaOut` (sin `visto_por_count` real -- recién creada, ver Tarea 7) |
| Ver una alerta | `GET /api/v1/alertas/<id>/` | `AlertaOut` |
| Resolver/cancelar | `PATCH /api/v1/alertas/<id>/resolver/` `{estado: "resuelta"\|"falsa_alarma"}` | `AlertaOut` |
| Marcar visto | `POST /api/v1/alertas/<id>/marcar_visto/` (sin cuerpo) | `AlertaOut` |

```ts
type MembresiaOut = {
  rol: "residente" | "delegado" | string;
  condominio: { id: number; nombre: string; [k: string]: unknown };
  unidad: { numero: string; [k: string]: unknown } | null;
  nombre: string;
  telefono: string;
};

type AlertaOut = {
  id: number;
  condominio_nombre: string;
  tipo: string;               // una de TIPO_CHOICES (ver src/alertas/tipos.ts, Tarea 4)
  tipo_display: string;
  estado: "activa" | "resuelta" | "falsa_alarma" | "auto_cerrada";
  estado_display: string;
  mensaje: string;
  latitud: string | null;     // DecimalField -> string en JSON
  longitud: string | null;
  fecha_creacion: string;     // ISO 8601
  autor_nombre: string;
  autor_unidad: string | null;
  autor_torre: string | null;
  resuelta_por: number | null;
  resuelta_por_nombre: string | null;
  resuelta_por_unidad: string | null;
  fecha_resolucion: string | null;
  visto_por_count: number | null; // null si quien consulta no es el autor
};
```

El push que manda el backend al crear o resolver una alerta lleva `data: {tipo: "alerta" | "alerta_resuelta", alerta_id: number}` (`alertas/services.py`) -- es la clave que la Tarea 6 usa para navegar al detalle correcto al tocar la notificación.

---

## File Structure

```
app_movil/                          (proyecto Expo nuevo, raíz propia con su propio package.json)
  app/                              (rutas de Expo Router)
    _layout.tsx                     (AuthProvider + guard de sesión)
    login.tsx
    sin-membresia.tsx               (pantalla para devquad: "modo administrador no disponible todavía")
    (vecino)/
      _layout.tsx                   (Drawer de Expo Router -- D-01)
      index.tsx                    (pantalla del botón de pánico)
      alertas/
        index.tsx                  (lista activas/historial)
        [id].tsx                   (detalle + visto por + cancelar)
  src/
    theme/
      colores.ts
      colores.test.ts
    auth/
      storage.ts
      storage.test.ts
      AuthContext.tsx
      AuthContext.test.tsx
    api/
      client.ts
      client.test.ts
      auth.ts
      alertas.ts
      dispositivos.ts
    alertas/
      tipos.ts
      colaEnvio.ts
      colaEnvio.test.ts
      enviarAlerta.ts
      enviarAlerta.test.ts
    components/
      BotonPanico.tsx
      BotonPanico.test.tsx
      SelectorTipoAlerta.tsx
      SelectorTipoAlerta.test.tsx
      VentanaCancelar.tsx
      VentanaCancelar.test.tsx
    ubicacion/
      gps.ts
      gps.test.ts
    notificaciones/
      push.ts
      push.test.ts
  package.json / tsconfig.json / app.json (generados por create-expo-app, luego editados)
```

---

### Task 1: Scaffolding del proyecto Expo + paleta de marca

**Files:**
- Create: `app_movil/` (proyecto completo, vía `npx create-expo-app@latest`)
- Create: `app_movil/src/theme/colores.ts`
- Create: `app_movil/src/theme/colores.test.ts`

**Interfaces:**
- Produces: `import { colores } from "../src/theme/colores"` -- objeto `{ primary, primaryDark, primaryDarker, secondary, accent, slate }`, usado por todos los componentes visuales de tareas siguientes.

- [ ] **Step 1: Crear el proyecto**

```bash
npx create-expo-app@latest app_movil --template default@latest
cd app_movil
```

Confirmar en `app_movil/package.json` que quedó con Expo Router (campo `"main": "expo-router/entry"` o equivalente) y TypeScript (existe `tsconfig.json`). Si la plantilla por defecto de la versión instalada no trae Expo Router, agregarlo (`npx expo install expo-router react-native-safe-area-context react-native-screens expo-linking expo-constants expo-status-bar`) y seguir la guía de migración oficial de Expo Router para esa versión del SDK instalada.

- [ ] **Step 2: Configurar testing**

```bash
npx expo install jest-expo jest @testing-library/react-native --dev
```

Agregar a `app_movil/package.json`:
```json
"jest": { "preset": "jest-expo" },
"scripts": { "test": "jest" }
```

- [ ] **Step 3: Escribir el test de la paleta (falla primero)**

```ts
// src/theme/colores.test.ts
import { colores } from "./colores";

test("usa los hex exactos de brand.css", () => {
  expect(colores).toEqual({
    primary: "#102D46",
    primaryDark: "#284E6B",
    primaryDarker: "#0A1B2A",
    secondary: "#708090",
    accent: "#0D9488",
    slate: "#5B7A8C",
  });
});
```

- [ ] **Step 4: Correr, confirmar que falla**

Run: `cd app_movil && npx jest src/theme/colores.test.ts --watchAll=false`
Expected: FAIL -- `colores.ts` no existe.

- [ ] **Step 5: Implementar `colores.ts`**

Exportar `const colores = { primary: "#102D46", primaryDark: "#284E6B", primaryDarker: "#0A1B2A", secondary: "#708090", accent: "#0D9488", slate: "#5B7A8C" }`.

- [ ] **Step 6: Correr, confirmar que pasa**

Run: `cd app_movil && npx jest src/theme/colores.test.ts --watchAll=false`
Expected: PASS

- [ ] **Step 7: Verificar que el proyecto arranca**

Run: `cd app_movil && npx expo start --web`
Expected: Metro bundler compila sin error y sirve la página web por defecto de la plantilla (confirmar visualmente o con el código de salida del bundler, luego cerrar con Ctrl+C -- este paso es manual, no hay aserción automática).

- [ ] **Step 8: Commit**

```bash
git add app_movil/
git commit -m "chore: scaffolding del proyecto Expo de la app movil + paleta de marca"
```

---

### Task 2: Almacenamiento de sesión + cliente API con refresco automático

**Files:**
- Create: `app_movil/src/auth/storage.ts`
- Create: `app_movil/src/auth/storage.test.ts`
- Create: `app_movil/src/api/client.ts`
- Create: `app_movil/src/api/client.test.ts`

**Interfaces:**
- Consumes: nada de tareas anteriores (solo la paleta, no usada acá).
- Produces:
  - `guardarTokens(access: string, refresh: string): Promise<void>`, `obtenerTokens(): Promise<{access: string, refresh: string} | null>`, `borrarTokens(): Promise<void>` (`storage.ts`) -- usados por la Tarea 3.
  - `apiFetch<T>(path: string, options?: RequestInit, requiereAuth: boolean = true): Promise<T>` (`client.ts`) -- función central que **todas** las tareas siguientes usan para hablar con el backend. Con `requiereAuth` en `true` (default), adjunta `Authorization: Bearer <access>`, y si la respuesta es 401, intenta refrescar una vez contra `/api/v1/auth/refresh/` y reintenta la request original una sola vez; si el refresh también falla, llama `borrarTokens()` y lanza un error con `.sesionExpirada = true` (para que `AuthContext`, en la Tarea 3, lo capture y mande a login). Con `requiereAuth = false` (lo usa únicamente `login()` en la Tarea 3, que todavía no tiene token), no adjunta `Authorization` y no intenta ningún refresh ante un 401 -- un 401 ahí es simplemente credenciales inválidas, se propaga tal cual.
  - `API_BASE_URL: string` -- de `process.env.EXPO_PUBLIC_API_URL`, sin un valor por defecto hardcodeado a producción (debe configurarse en `app_movil/.env` o vía EAS, ver Step 5).

- [ ] **Step 1: Escribir el test de storage (falla primero)**

```ts
// src/auth/storage.test.ts
import { guardarTokens, obtenerTokens, borrarTokens } from "./storage";

test("guarda y devuelve los tokens", async () => {
  await guardarTokens("acc1", "ref1");
  expect(await obtenerTokens()).toEqual({ access: "acc1", refresh: "ref1" });
});

test("borrarTokens limpia el almacenamiento", async () => {
  await guardarTokens("acc1", "ref1");
  await borrarTokens();
  expect(await obtenerTokens()).toBeNull();
});
```

Mockear `expo-secure-store` con `jest.mock("expo-secure-store", ...)` (un Map en memoria simulando `getItemAsync`/`setItemAsync`/`deleteItemAsync`).

- [ ] **Step 2: Correr, confirmar que falla**

Run: `cd app_movil && npx jest src/auth/storage.test.ts --watchAll=false`
Expected: FAIL -- `storage.ts` no existe.

- [ ] **Step 3: Implementar `storage.ts`**

```bash
npx expo install expo-secure-store
```

`Platform.OS === "web"` -> usar `localStorage.getItem/setItem/removeItem` bajo las mismas claves (`mibarrio.access`, `mibarrio.refresh`); en cualquier otro caso, usar `SecureStore.getItemAsync/setItemAsync/deleteItemAsync`. Misma firma de las 3 funciones en ambos casos.

- [ ] **Step 4: Correr, confirmar que pasa**

Run: `cd app_movil && npx jest src/auth/storage.test.ts --watchAll=false`
Expected: PASS

- [ ] **Step 5: Escribir los tests del cliente API (fallan primero)**

```ts
// src/api/client.test.ts
import { apiFetch } from "./client";
import * as storage from "../auth/storage";

test("adjunta el Authorization header con el access token guardado", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue({ access: "acc1", refresh: "ref1" });
  global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ ok: true }) });
  await apiFetch("/api/v1/auth/me/");
  expect(global.fetch).toHaveBeenCalledWith(
    expect.stringContaining("/api/v1/auth/me/"),
    expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Bearer acc1" }) })
  );
});

test("ante un 401, refresca una vez y reintenta la request original", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue({ access: "vencido", refresh: "ref1" });
  const guardarSpy = jest.spyOn(storage, "guardarTokens").mockResolvedValue();
  global.fetch = jest.fn()
    .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({}) })
    .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ access: "nuevo" }) })
    .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ ok: true }) });
  const resultado = await apiFetch("/api/v1/auth/me/");
  expect(resultado).toEqual({ ok: true });
  expect(guardarSpy).toHaveBeenCalledWith("nuevo", "ref1");
  expect(global.fetch).toHaveBeenCalledTimes(3);
});

test("si el refresh también falla, borra los tokens y lanza sesionExpirada", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue({ access: "vencido", refresh: "vencido" });
  const borrarSpy = jest.spyOn(storage, "borrarTokens").mockResolvedValue();
  global.fetch = jest.fn()
    .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({}) })
    .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({}) });
  await expect(apiFetch("/api/v1/auth/me/")).rejects.toMatchObject({ sesionExpirada: true });
  expect(borrarSpy).toHaveBeenCalled();
});
```

- [ ] **Step 6: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest src/api/client.test.ts --watchAll=false`
Expected: FAIL -- `client.ts` no existe.

- [ ] **Step 7: Implementar `client.ts`**

La lógica de refresh-y-reintento-una-sola-vez es el único punto no trivial; el resto (armar headers, parsear JSON) es directo a partir de la firma. `requiereAuth = false` salta por completo el bloque de `Authorization`/refresh (ver Interfaces) -- la Tarea 3 es quien primero lo necesita, para el login.

- [ ] **Step 8: Correr, confirmar que pasan**

Run: `cd app_movil && npx jest src/api/client.test.ts --watchAll=false`
Expected: PASS

- [ ] **Step 8b: Test de `requiereAuth = false` (falla primero, implementación ya hecha en el Step 7 -- confirma el caso que la Tarea 3 va a consumir)**

```ts
test("con requiereAuth=false, no adjunta Authorization ni reintenta ante un 401", async () => {
  const obtenerSpy = jest.spyOn(storage, "obtenerTokens");
  global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({ detail: "credenciales invalidas" }) });
  await expect(apiFetch("/api/v1/auth/login/", { method: "POST" }, false)).rejects.toBeDefined();
  expect(obtenerSpy).not.toHaveBeenCalled();
  expect(global.fetch).toHaveBeenCalledTimes(1);
});
```

Run: `cd app_movil && npx jest src/api/client.test.ts --watchAll=false`
Expected: PASS (si falla, revisar que el Step 7 ya haya implementado la rama `requiereAuth = false` -- si no, implementarla ahora y volver a correr).

- [ ] **Step 9: Suite completa + commit**

Run: `cd app_movil && npx jest --watchAll=false`
Expected: todos los tests existentes en verde.

```bash
git add app_movil/src/auth app_movil/src/api app_movil/package.json
git commit -m "feat: almacenamiento de sesion y cliente API con refresco automatico de token"
```

---

### Task 3: Autenticación -- AuthContext + pantalla de login

**Files:**
- Create: `app_movil/src/api/auth.ts`
- Create: `app_movil/src/auth/AuthContext.tsx`
- Create: `app_movil/src/auth/AuthContext.test.tsx`
- Create: `app_movil/app/_layout.tsx`
- Create: `app_movil/app/login.tsx`
- Create: `app_movil/app/sin-membresia.tsx`

**Interfaces:**
- Consumes: `apiFetch` (Tarea 2), `guardarTokens`/`obtenerTokens`/`borrarTokens` (Tarea 2).
- Produces:
  - `login(username: string, password: string): Promise<{access: string, refresh: string, membresia: MembresiaOut | null}>` (`api/auth.ts`, `POST /api/v1/auth/login/`).
  - `useAuth()` hook + `<AuthProvider>` (`AuthContext.tsx`), exponiendo `{ estado: "cargando" | "sin_sesion" | "sin_membresia" | "autenticado", membresia: MembresiaOut | null, iniciarSesion(username, password): Promise<void>, cerrarSesion(): Promise<void> }` -- usado por el guard de rutas (este mismo archivo) y por todas las pantallas que necesiten saber quién es el usuario actual (Tareas 4-7).

- [ ] **Step 1: Escribir los tests de `AuthContext` (fallan primero)**

```tsx
// src/auth/AuthContext.test.tsx
import { render, screen, waitFor } from "@testing-library/react-native";
import { Text } from "react-native";
import { AuthProvider, useAuth } from "./AuthContext";
import * as authApi from "../api/auth";
import * as storage from "./storage";

function Sonda() {
  const { estado, membresia } = useAuth();
  return <Text>{estado}:{membresia?.nombre ?? "-"}</Text>;
}

test("sin tokens guardados, arranca en sin_sesion", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue(null);
  render(<AuthProvider><Sonda /></AuthProvider>);
  await waitFor(() => screen.getByText("sin_sesion:-"));
});

test("login exitoso con membresia pasa a autenticado", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue(null);
  jest.spyOn(storage, "guardarTokens").mockResolvedValue();
  jest.spyOn(authApi, "login").mockResolvedValue({
    access: "a", refresh: "r", membresia: { nombre: "Ana", rol: "residente", condominio: { id: 1, nombre: "X" }, unidad: null, telefono: "" },
  });
  let auth: ReturnType<typeof useAuth>;
  function Capturador() { auth = useAuth(); return null; }
  render(<AuthProvider><Capturador /></AuthProvider>);
  await waitFor(() => expect(auth.estado).toBe("sin_sesion"));
  await auth!.iniciarSesion("ana", "clave");
  await waitFor(() => expect(auth.estado).toBe("autenticado"));
  expect(auth!.membresia?.nombre).toBe("Ana");
});

test("login exitoso sin membresia (devquad) pasa a sin_membresia, no a autenticado", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue(null);
  jest.spyOn(storage, "guardarTokens").mockResolvedValue();
  jest.spyOn(authApi, "login").mockResolvedValue({ access: "a", refresh: "r", membresia: null });
  let auth: ReturnType<typeof useAuth>;
  function Capturador() { auth = useAuth(); return null; }
  render(<AuthProvider><Capturador /></AuthProvider>);
  await waitFor(() => expect(auth.estado).toBe("sin_sesion"));
  await auth!.iniciarSesion("devquad", "clave");
  await waitFor(() => expect(auth.estado).toBe("sin_membresia"));
});
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest src/auth/AuthContext.test.tsx --watchAll=false`
Expected: FAIL -- `AuthContext.tsx`/`api/auth.ts` no existen.

- [ ] **Step 3: Implementar `api/auth.ts` y `AuthContext.tsx`**

`login()` llama `apiFetch("/api/v1/auth/login/", { method: "POST", body: JSON.stringify({ username, password }) }, false)` -- el tercer argumento `requiereAuth = false` ya construido en la Tarea 2 (Step 8b), porque este es el único llamado de toda la app que no tiene sesión previa. `AuthProvider` al montar intenta `obtenerTokens()`; si hay, confía en el `membresia` que vino del login y queda `autenticado` (no reconsulta `/auth/me/` al arrancar -- mantiene la Tarea 3 simple; refrescar membresía en caliente no es parte de esta tanda).

- [ ] **Step 4: Correr, confirmar que pasan**

Run: `cd app_movil && npx jest src/auth/AuthContext.test.tsx --watchAll=false`
Expected: PASS

- [ ] **Step 5: Pantalla de login + guard de rutas (sin test automático -- UI de navegación)**

`app/login.tsx`: formulario usuario/contraseña, llama `iniciarSesion`, muestra el mensaje de error si la promesa rechaza. `app/_layout.tsx`: envuelve todo en `<AuthProvider>`; usando `useAuth().estado`, redirige (`router.replace`) a `/login` si `sin_sesion`, a `/sin-membresia` si `sin_membresia`, a `/(vecino)` si `autenticado`. `app/sin-membresia.tsx`: mensaje fijo "El modo administrador todavía no está disponible en esta versión de la app -- usa el panel web." + botón para cerrar sesión.

- [ ] **Step 6: Suite completa + commit**

Run: `cd app_movil && npx jest --watchAll=false`
Expected: todos los tests en verde.

```bash
git add app_movil/src/api/auth.ts app_movil/src/auth app_movil/app
git commit -m "feat: autenticacion -- AuthContext, login y guard de rutas"
```

---

### Task 4: Botón de pánico -- gesto de 2 segundos + selector de tipo (D-01..D-03)

**Files:**
- Create: `app_movil/src/alertas/tipos.ts`
- Create: `app_movil/src/components/BotonPanico.tsx`
- Create: `app_movil/src/components/BotonPanico.test.tsx`
- Create: `app_movil/src/components/SelectorTipoAlerta.tsx`
- Create: `app_movil/src/components/SelectorTipoAlerta.test.tsx`

**Interfaces:**
- Consumes: `colores` (Tarea 1).
- Produces:
  - `TIPOS_ALERTA: {valor: string, etiqueta: string}[]` (`tipos.ts`) -- espejo exacto de `TIPO_CHOICES` en `alertas/models.py` (mismos 12 valores/etiquetas; si el backend agrega un tipo nuevo, este archivo se actualiza a mano, igual que ya documenta el propio modelo Django sobre `TITULOS_POR_TIPO`).
  - `<BotonPanico onConfirmar={(tipo: string) => void} tipoSeleccionado={string} />` -- componente del botón grande; usado por `app/(vecino)/index.tsx` en la Tarea 5.
  - `<SelectorTipoAlerta valor={string} onCambiar={(tipo: string) => void} />` -- control chico al lado del botón.

- [ ] **Step 1: Escribir `tipos.ts` (sin test -- es una constante de datos, espejo 1:1 del backend)**

Copiar los 12 pares valor/etiqueta de `TIPO_CHOICES` (`alertas/models.py:5-18`) tal cual.

- [ ] **Step 2: Escribir los tests de `BotonPanico` (fallan primero)**

```tsx
// src/components/BotonPanico.test.tsx
import { render, fireEvent, screen } from "@testing-library/react-native";
import { BotonPanico } from "./BotonPanico";

beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());

test("mantener apretado 2000ms confirma con el tipo seleccionado", () => {
  const onConfirmar = jest.fn();
  render(<BotonPanico onConfirmar={onConfirmar} tipoSeleccionado="otro" />);
  fireEvent(screen.getByTestId("boton-panico"), "pressIn");
  jest.advanceTimersByTime(2000);
  expect(onConfirmar).toHaveBeenCalledWith("otro");
});

test("soltar antes de 2000ms no confirma nada", () => {
  const onConfirmar = jest.fn();
  render(<BotonPanico onConfirmar={onConfirmar} tipoSeleccionado="otro" />);
  const boton = screen.getByTestId("boton-panico");
  fireEvent(boton, "pressIn");
  jest.advanceTimersByTime(1000);
  fireEvent(boton, "pressOut");
  jest.advanceTimersByTime(2000);
  expect(onConfirmar).not.toHaveBeenCalled();
});

test("usa el tipo pasado por prop, no siempre 'otro'", () => {
  const onConfirmar = jest.fn();
  render(<BotonPanico onConfirmar={onConfirmar} tipoSeleccionado="incendio" />);
  fireEvent(screen.getByTestId("boton-panico"), "pressIn");
  jest.advanceTimersByTime(2000);
  expect(onConfirmar).toHaveBeenCalledWith("incendio");
});
```

- [ ] **Step 3: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest src/components/BotonPanico.test.tsx --watchAll=false`
Expected: FAIL -- `BotonPanico.tsx` no existe.

- [ ] **Step 4: Implementar `BotonPanico.tsx`**

`Pressable` con `testID="boton-panico"`, `onPressIn` arranca `setTimeout(() => onConfirmar(tipoSeleccionado), 2000)` guardado en un ref, `onPressOut` lo limpia con `clearTimeout`. Fondo `colores.primary` (o un rojo de alerta si se prefiere -- a criterio visual, D-01 solo exige que sea grande y sin competencia). Un indicador visual de progreso durante el hold es deseable pero no obligatorio para esta tarea (UI, no hay test que lo exija).

- [ ] **Step 5: Correr, confirmar que pasan**

Run: `cd app_movil && npx jest src/components/BotonPanico.test.tsx --watchAll=false`
Expected: PASS

- [ ] **Step 6: Escribir los tests de `SelectorTipoAlerta` (fallan primero)**

```tsx
// src/components/SelectorTipoAlerta.test.tsx
import { render, fireEvent, screen } from "@testing-library/react-native";
import { SelectorTipoAlerta } from "./SelectorTipoAlerta";

test("al elegir un tipo de la lista, llama a onCambiar con ese valor", () => {
  const onCambiar = jest.fn();
  render(<SelectorTipoAlerta valor="otro" onCambiar={onCambiar} />);
  fireEvent.press(screen.getByTestId("selector-tipo-abrir"));
  fireEvent.press(screen.getByText("Incendio"));
  expect(onCambiar).toHaveBeenCalledWith("incendio");
});
```

- [ ] **Step 7: Correr, confirmar que falla**

Run: `cd app_movil && npx jest src/components/SelectorTipoAlerta.test.tsx --watchAll=false`
Expected: FAIL -- `SelectorTipoAlerta.tsx` no existe.

- [ ] **Step 8: Implementar `SelectorTipoAlerta.tsx`**

Un control chico (`testID="selector-tipo-abrir"`) que al tocarlo despliega la lista de `TIPOS_ALERTA` (un `Modal` o desplegable simple); tocar una opción llama `onCambiar(valor)` y cierra la lista.

- [ ] **Step 9: Correr, confirmar que pasa**

Run: `cd app_movil && npx jest src/components/SelectorTipoAlerta.test.tsx --watchAll=false`
Expected: PASS

- [ ] **Step 10: Suite completa + commit**

Run: `cd app_movil && npx jest --watchAll=false`
Expected: todos los tests en verde.

```bash
git add app_movil/src/alertas/tipos.ts app_movil/src/components/BotonPanico.tsx app_movil/src/components/BotonPanico.test.tsx app_movil/src/components/SelectorTipoAlerta.tsx app_movil/src/components/SelectorTipoAlerta.test.tsx
git commit -m "feat: boton de panico (press-and-hold 2s) y selector de tipo de alerta"
```

---

### Task 5: Envío de alerta -- ubicación automática + cola de reintento + ventana de cancelar (D-04)

**Files:**
- Create: `app_movil/src/ubicacion/gps.ts`
- Create: `app_movil/src/ubicacion/gps.test.ts`
- Create: `app_movil/src/api/alertas.ts`
- Create: `app_movil/src/alertas/colaEnvio.ts`
- Create: `app_movil/src/alertas/colaEnvio.test.ts`
- Create: `app_movil/src/alertas/enviarAlerta.ts`
- Create: `app_movil/src/alertas/enviarAlerta.test.ts`
- Create: `app_movil/src/components/VentanaCancelar.tsx`
- Create: `app_movil/src/components/VentanaCancelar.test.tsx`
- Modify: `app_movil/app/(vecino)/index.tsx` (crear si no existe -- pantalla del botón de pánico, integra Tarea 4 + esta tarea)

**Interfaces:**
- Consumes: `apiFetch` (Tarea 2), `BotonPanico`/`SelectorTipoAlerta` (Tarea 4).
- Produces:
  - `obtenerUbicacionActual(): Promise<{latitud: number, longitud: number} | null>` (`gps.ts`) -- nunca lanza, devuelve `null` si el permiso se niega o no hay fix de GPS disponible.
  - `crearAlerta(payload): Promise<AlertaOut>`, `resolverAlerta(id, estado): Promise<AlertaOut>` (`api/alertas.ts`) -- usadas también por la Tarea 7.
  - `encolarAlerta(payload)`, `procesarCola(): Promise<void>` (`colaEnvio.ts`) -- cola persistida en `AsyncStorage`, procesada en orden FIFO, cada item se quita de la cola recién cuando su POST confirma éxito (nunca antes), y `procesarCola` se detiene en el primer fallo (no salta al siguiente, para no reordenar).
  - `enviarAlerta(tipo, latitud, longitud): Promise<AlertaOut | {encolada: true}>` (`enviarAlerta.ts`) -- orquesta: intenta `crearAlerta` directo; si falla por red, llama `encolarAlerta` y devuelve `{encolada: true}` en vez de lanzar.
  - `<VentanaCancelar alertaId={number} onCancelada={() => void} />` -- cuenta regresiva de 10s con botón "Cancelar, fue un error".

- [ ] **Step 1: Escribir los tests de `gps.ts` (fallan primero)**

```ts
// src/ubicacion/gps.test.ts
import * as Location from "expo-location";
import { obtenerUbicacionActual } from "./gps";

jest.mock("expo-location");

test("con permiso concedido, devuelve latitud/longitud", async () => {
  (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({ status: "granted" });
  (Location.getCurrentPositionAsync as jest.Mock).mockResolvedValue({ coords: { latitude: -33.45, longitude: -70.65 } });
  expect(await obtenerUbicacionActual()).toEqual({ latitud: -33.45, longitud: -70.65 });
});

test("con permiso denegado, devuelve null sin lanzar", async () => {
  (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({ status: "denied" });
  await expect(obtenerUbicacionActual()).resolves.toBeNull();
});
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest src/ubicacion/gps.test.ts --watchAll=false`
Expected: FAIL -- `gps.ts` no existe.

- [ ] **Step 3: Implementar `gps.ts`**

```bash
npx expo install expo-location
```

- [ ] **Step 4: Correr, confirmar que pasan**

Run: `cd app_movil && npx jest src/ubicacion/gps.test.ts --watchAll=false`
Expected: PASS

- [ ] **Step 5: Escribir `api/alertas.ts` (sin test propio -- son dos llamadas directas a `apiFetch`, ya cubierto por los tests de `client.ts`)**

`crearAlerta(payload)` -> `apiFetch("/api/v1/alertas/", { method: "POST", body: JSON.stringify(payload) })`. `resolverAlerta(id, estado)` -> `apiFetch(\`/api/v1/alertas/${id}/resolver/\`, { method: "PATCH", body: JSON.stringify({ estado }) })`.

- [ ] **Step 6: Escribir los tests de la cola (fallan primero)**

```ts
// src/alertas/colaEnvio.test.ts
import { encolarAlerta, procesarCola } from "./colaEnvio";
import * as alertasApi from "../api/alertas";

test("procesa los items encolados en orden y los quita al confirmar exito", async () => {
  await encolarAlerta({ tipo: "otro" });
  await encolarAlerta({ tipo: "incendio" });
  const crearSpy = jest.spyOn(alertasApi, "crearAlerta").mockResolvedValue({ id: 1 } as any);
  await procesarCola();
  expect(crearSpy.mock.calls.map(c => c[0].tipo)).toEqual(["otro", "incendio"]);
});

test("si un item falla, se detiene sin saltar al siguiente (no reordena)", async () => {
  await encolarAlerta({ tipo: "otro" });
  await encolarAlerta({ tipo: "incendio" });
  const crearSpy = jest.spyOn(alertasApi, "crearAlerta")
    .mockRejectedValueOnce(new Error("sin red"))
    .mockResolvedValueOnce({ id: 2 } as any);
  await procesarCola();
  expect(crearSpy).toHaveBeenCalledTimes(1);
});
```

- [ ] **Step 7: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest src/alertas/colaEnvio.test.ts --watchAll=false`
Expected: FAIL -- `colaEnvio.ts` no existe.

- [ ] **Step 8: Implementar `colaEnvio.ts`**

```bash
npx expo install @react-native-async-storage/async-storage
```

Guardar la cola como un array JSON bajo una única clave (`mibarrio.colaAlertas`). `procesarCola` lee la cola completa, itera en orden, y en cada iteración exitosa vuelve a persistir la cola ya sin ese item (para que un fallo en el item 2 deje al item 1 ya marcado como enviado, no reintentado).

- [ ] **Step 9: Correr, confirmar que pasan**

Run: `cd app_movil && npx jest src/alertas/colaEnvio.test.ts --watchAll=false`
Expected: PASS

- [ ] **Step 10: Escribir los tests de `enviarAlerta` (fallan primero)**

```ts
// src/alertas/enviarAlerta.test.ts
import { enviarAlerta } from "./enviarAlerta";
import * as alertasApi from "../api/alertas";
import * as cola from "./colaEnvio";

test("si crearAlerta funciona, devuelve la alerta creada", async () => {
  jest.spyOn(alertasApi, "crearAlerta").mockResolvedValue({ id: 5 } as any);
  const resultado = await enviarAlerta("otro", null, null);
  expect(resultado).toEqual({ id: 5 });
});

test("si crearAlerta falla, encola y devuelve {encolada: true} sin lanzar", async () => {
  jest.spyOn(alertasApi, "crearAlerta").mockRejectedValue(new Error("sin red"));
  const encolarSpy = jest.spyOn(cola, "encolarAlerta").mockResolvedValue();
  const resultado = await enviarAlerta("otro", null, null);
  expect(resultado).toEqual({ encolada: true });
  expect(encolarSpy).toHaveBeenCalled();
});
```

- [ ] **Step 11: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest src/alertas/enviarAlerta.test.ts --watchAll=false`
Expected: FAIL -- `enviarAlerta.ts` no existe.

- [ ] **Step 12: Implementar `enviarAlerta.ts`**

- [ ] **Step 13: Correr, confirmar que pasan**

Run: `cd app_movil && npx jest src/alertas/enviarAlerta.test.ts --watchAll=false`
Expected: PASS

- [ ] **Step 14: Escribir los tests de `VentanaCancelar` (fallan primero)**

```tsx
// src/components/VentanaCancelar.test.tsx
import { render, fireEvent, screen } from "@testing-library/react-native";
import { VentanaCancelar } from "./VentanaCancelar";
import * as alertasApi from "../api/alertas";

beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());

test("tocar Cancelar dentro de la ventana llama a resolverAlerta con falsa_alarma", async () => {
  const resolverSpy = jest.spyOn(alertasApi, "resolverAlerta").mockResolvedValue({} as any);
  const onCancelada = jest.fn();
  render(<VentanaCancelar alertaId={9} onCancelada={onCancelada} />);
  fireEvent.press(screen.getByText(/Cancelar, fue un error/i));
  await Promise.resolve();
  expect(resolverSpy).toHaveBeenCalledWith(9, "falsa_alarma");
  expect(onCancelada).toHaveBeenCalled();
});

test("el boton desaparece despues de 10 segundos", () => {
  render(<VentanaCancelar alertaId={9} onCancelada={jest.fn()} />);
  jest.advanceTimersByTime(10000);
  expect(screen.queryByText(/Cancelar, fue un error/i)).toBeNull();
});
```

- [ ] **Step 15: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest src/components/VentanaCancelar.test.tsx --watchAll=false`
Expected: FAIL -- `VentanaCancelar.tsx` no existe.

- [ ] **Step 16: Implementar `VentanaCancelar.tsx`**

- [ ] **Step 17: Correr, confirmar que pasan**

Run: `cd app_movil && npx jest src/components/VentanaCancelar.test.tsx --watchAll=false`
Expected: PASS

- [ ] **Step 18: Integrar en la pantalla del botón de pánico (sin test automático -- composición de UI)**

`app/(vecino)/index.tsx`: estado local de tipo seleccionado (default `"otro"`); `<BotonPanico onConfirmar={tipo => enviarAlerta(tipo, ...(await obtenerUbicacionActual() ?? {latitud: null, longitud: null}))} tipoSeleccionado={tipo} />` + `<SelectorTipoAlerta />`; tras un envío exitoso (no encolado), muestra `<VentanaCancelar alertaId={resultado.id} />`.

- [ ] **Step 19: Suite completa + commit**

Run: `cd app_movil && npx jest --watchAll=false`
Expected: todos los tests en verde.

```bash
git add app_movil/src/ubicacion app_movil/src/api/alertas.ts app_movil/src/alertas/colaEnvio.ts app_movil/src/alertas/colaEnvio.test.ts app_movil/src/alertas/enviarAlerta.ts app_movil/src/alertas/enviarAlerta.test.ts app_movil/src/components/VentanaCancelar.tsx app_movil/src/components/VentanaCancelar.test.tsx app_movil/app
git commit -m "feat: envio de alerta -- ubicacion automatica, cola de reintento y ventana de cancelar"
```

---

### Task 6: Notificaciones push -- registro y recepción (D-04, consume infra ya existente)

**Files:**
- Create: `app_movil/src/notificaciones/push.ts`
- Create: `app_movil/src/notificaciones/push.test.ts`
- Modify: `app_movil/src/auth/AuthContext.tsx` (llamar al registro tras un login exitoso)
- Modify: `app_movil/app/_layout.tsx` (listener de notificación tocada -> navegar al detalle)

**Interfaces:**
- Consumes: `apiFetch` (Tarea 2), `estado`/`iniciarSesion` de `AuthContext` (Tarea 3).
- Produces: `registrarDispositivoPush(): Promise<void>` (`push.ts`) -- no-opera (no pide permiso, no llama al backend) si `Platform.OS === "web"`; en nativo, pide permiso, obtiene el Expo push token, y hace `POST /api/v1/dispositivos/` con `{token, plataforma: Platform.OS}`. Si el permiso se niega, retorna sin lanzar y sin llamar al backend.

- [ ] **Step 1: Escribir los tests de `push.ts` (fallan primero)**

```ts
// src/notificaciones/push.test.ts
import { Platform } from "react-native";
import * as Notifications from "expo-notifications";
import { registrarDispositivoPush } from "./push";
import * as dispositivosApi from "../api/dispositivos";

jest.mock("expo-notifications");

test("en Web, no pide permiso ni registra nada", async () => {
  Platform.OS = "web";
  const registrarSpy = jest.spyOn(dispositivosApi, "registrarDispositivo").mockResolvedValue();
  await registrarDispositivoPush();
  expect(registrarSpy).not.toHaveBeenCalled();
});

test("en nativo con permiso concedido, registra el token obtenido", async () => {
  Platform.OS = "android";
  (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: "undetermined" });
  (Notifications.requestPermissionsAsync as jest.Mock).mockResolvedValue({ status: "granted" });
  (Notifications.getExpoPushTokenAsync as jest.Mock).mockResolvedValue({ data: "ExponentPushToken[abc]" });
  const registrarSpy = jest.spyOn(dispositivosApi, "registrarDispositivo").mockResolvedValue();
  await registrarDispositivoPush();
  expect(registrarSpy).toHaveBeenCalledWith("ExponentPushToken[abc]", "android");
});

test("en nativo con permiso denegado, no registra nada ni lanza", async () => {
  Platform.OS = "ios";
  (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: "undetermined" });
  (Notifications.requestPermissionsAsync as jest.Mock).mockResolvedValue({ status: "denied" });
  const registrarSpy = jest.spyOn(dispositivosApi, "registrarDispositivo").mockResolvedValue();
  await expect(registrarDispositivoPush()).resolves.not.toThrow();
  expect(registrarSpy).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest src/notificaciones/push.test.ts --watchAll=false`
Expected: FAIL -- `push.ts`/`api/dispositivos.ts` no existen.

- [ ] **Step 3: Implementar `api/dispositivos.ts` y `push.ts`**

```bash
npx expo install expo-notifications
```

`registrarDispositivo(token, plataforma)` en `api/dispositivos.ts` -> `apiFetch("/api/v1/dispositivos/", { method: "POST", body: JSON.stringify({ token, plataforma }) })`.

- [ ] **Step 4: Correr, confirmar que pasan**

Run: `cd app_movil && npx jest src/notificaciones/push.test.ts --watchAll=false`
Expected: PASS

- [ ] **Step 5: Conectar al login y al listener de notificación tocada (sin test automático -- requiere entorno nativo real)**

En `AuthContext.tsx`, llamar `registrarDispositivoPush()` (sin esperar ni bloquear la UI) justo después de que `iniciarSesion` deja el estado en `autenticado`. En `app/_layout.tsx`, `Notifications.addNotificationResponseReceivedListener` -> leer `response.notification.request.content.data.alerta_id` y `router.push(\`/alertas/${alerta_id}\`)`.

- [ ] **Step 6: Suite completa + commit**

Run: `cd app_movil && npx jest --watchAll=false`
Expected: todos los tests en verde.

```bash
git add app_movil/src/notificaciones app_movil/src/api/dispositivos.ts app_movil/src/auth/AuthContext.tsx app_movil/app/_layout.tsx
git commit -m "feat: registro de push notifications y navegacion al tocar una notificacion"
```

---

### Task 7: Lista de alertas activas/historial + detalle con "visto por" (D-05)

**Files:**
- Modify: `app_movil/src/api/alertas.ts` (agregar `listarAlertas`, `marcarVisto`)
- Create: `app_movil/app/(vecino)/alertas/index.tsx`
- Create: `app_movil/app/(vecino)/alertas/[id].tsx`

**Interfaces:**
- Consumes: `apiFetch` (Tarea 2), `membresia` de `AuthContext` (Tarea 3) -- para comparar `autor_nombre`/identidad y decidir si mostrar el botón "Marcar como visto" (se oculta si `visto_por_count` ya viene `null`, que es exactamente la señal del backend de "no sos el autor").
- Produces: `listarAlertas(estado?: string): Promise<AlertaOut[]>`, `marcarVisto(id: number): Promise<AlertaOut>` (agregados a `api/alertas.ts`).

- [ ] **Step 1: Escribir los tests de `listarAlertas`/`marcarVisto` (fallan primero)**

```ts
// agregar a un archivo de test de api/alertas, ej. src/api/alertas.test.ts
import { listarAlertas, marcarVisto } from "./alertas";
import { apiFetch } from "./client";

jest.mock("./client");

test("listarAlertas sin estado pide /api/v1/alertas/ sin query", async () => {
  (apiFetch as jest.Mock).mockResolvedValue([]);
  await listarAlertas();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/alertas/");
});

test("listarAlertas con estado arma el query param", async () => {
  (apiFetch as jest.Mock).mockResolvedValue([]);
  await listarAlertas("activa");
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/alertas/?estado=activa");
});

test("marcarVisto pega al endpoint correcto", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ id: 3 });
  await marcarVisto(3);
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/alertas/3/marcar_visto/", { method: "POST" });
});
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest src/api/alertas.test.ts --watchAll=false`
Expected: FAIL -- `listarAlertas`/`marcarVisto` no existen todavía.

- [ ] **Step 3: Implementar ambas funciones en `api/alertas.ts`**

- [ ] **Step 4: Correr, confirmar que pasan**

Run: `cd app_movil && npx jest src/api/alertas.test.ts --watchAll=false`
Expected: PASS

- [ ] **Step 5: Pantallas de lista y detalle (sin test automático -- composición de UI sobre funciones ya probadas)**

`app/(vecino)/alertas/index.tsx`: dos secciones, "Activas" (`listarAlertas("activa")`) e "Historial" (`listarAlertas("recientes")`), cada fila navega a `/alertas/[id]`. `app/(vecino)/alertas/[id].tsx`: muestra todos los campos de `AlertaOut`; la fila "Visto por N vecino(s)" solo se renderiza si `visto_por_count !== null`; si `visto_por_count === null` (no soy el autor) y el `estado` es `"activa"`, muestra un botón "Marcar como visto" que llama `marcarVisto(id)` y refresca la pantalla con la respuesta.

- [ ] **Step 6: Suite completa + commit**

Run: `cd app_movil && npx jest --watchAll=false`
Expected: todos los tests en verde.

```bash
git add app_movil/src/api/alertas.ts app_movil/src/api/alertas.test.ts app_movil/app/\(vecino\)/alertas
git commit -m "feat: lista de alertas activas-historial y detalle con visto-por"
```

---

## Self-Review (hecho al escribir este plan)

**Cobertura del spec (alcance de esta tanda -- "Núcleo"):** login (Tarea 3), botón de pánico + D-01/D-02/D-03 (Tarea 4), las 4 mejoras de D-04 completas -- ubicación (Tarea 5), reintento mientras la app vive (Tarea 5), ventana de cancelar de 10s con push inmediato ya garantizado por el backend sin tocarlo (Tarea 5), modo silencioso explícitamente no construido (Non-goal, respetado); recibir notificaciones (Tarea 6); ver alertas activas/historial con "visto por" consumiendo D-05 ya construido en el backend (Tarea 7). D-06 (foto) y D-07 (modo administrador) quedan fuera a propósito, son Tanda 3/Non-goal.

**Review Focus:** los 5 puntos tienen tarea y test propios -- doble-401/sesión expirada (Tarea 2), permiso de ubicación denegado (Tarea 5), permiso de push denegado (Tarea 6), cola sin duplicar/reordenar (Tarea 5), devquad sin Membresia (Tarea 3).

**Consistencia de tipos:** `AlertaOut`/`MembresiaOut` quedan fijados una sola vez en la tabla de endpoints y se reusan tal cual en las Tareas 3 y 7 -- ninguna tarea redefine su propio shape.

**Proporción:** 7 tareas, cada una con una sola responsabilidad nueva (storage, cliente HTTP, auth, botón, envío+cola+cancelar, push, lista/detalle) -- el envío (Tarea 5) es la más grande porque empaqueta las 4 mejoras de D-04, que el propio spec ya agrupa como una sola decisión (D-04).

## Qué queda a criterio de quien lo construya

- Diseño visual exacto del botón de pánico (indicador de progreso durante el hold, íconos, animaciones) -- el plan fija el comportamiento (2000ms, cancela al soltar) y los hex de marca, no el detalle pixel a pixel.
- Si el Drawer (D-01) se abre con un ícono fijo en una esquina o con gesto de borde -- ambos cumplen "no competir con el botón".
- Mensaje exacto y diseño de la pantalla `sin-membresia.tsx` -- el plan fija el comportamiento (no crashear, no confundirse con un error), no la redacción final.
- Mecanismo exacto de cuándo se dispara `procesarCola()` en segundo plano (ej. al detectar reconexión vía `NetInfo`, al volver la app a foreground, con un intervalo corto) -- el plan fija que debe reintentarse mientras la app sigue viva y en el orden correcto, no el trigger exacto.
- Tandas 2-4 de la app (avisos/directorio/perfil/invitar, modo administrador, pagos/foto/modo silencioso) quedan para planes aparte, uno por tanda, igual que este mismo documento se escribió aparte del resto de la Fase 2.

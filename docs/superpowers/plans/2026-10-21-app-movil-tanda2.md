# App móvil de Mi Barrio+ -- Tanda 2 (Lo demás del vecino) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Completar el resto de lo que un vecino (residente o delegado) hace en la web, sobre la base ya construida en la Tanda 1 (Núcleo): avisos, directorio, editar "Mi perfil" e invitar/compartir. Al terminar, la app cubre el mismo alcance de la web para un residente -- lo único que falta después de esto es el modo administrador de devquad (Tanda 3) y pagos/foto/modo silencioso (Tanda 4), que quedan fuera de este plan.

**Architecture:** Mismo patrón ya establecido en la Tanda 1: un módulo `api/<recurso>.ts` por recurso (usa `apiFetch` de `src/api/client.ts`), una pantalla por recurso bajo `src/app/(vecino)/<recurso>/`, registrada en el Drawer de `(vecino)/_layout.tsx`. Ningún estado nuevo de navegación ni librería nueva -- avisos se muestran en una sola lista con el cuerpo completo (igual que `core/templates/core/inicio.html`, sin pantalla de detalle aparte), directorio es una lista simple, mi perfil es un formulario, invitar es una pantalla con un botón que abre la hoja de compartir nativa (`Share` de `react-native`, ya incluido, sin dependencia nueva).

**Tech Stack:** El mismo de la Tanda 1 (Expo Router, TypeScript, jest-expo, @testing-library/react-native). Sin paquetes nuevos.

**Spec:** `docs/superpowers/specs/2026-10-19-app-movil-mi-barrio-design.md` (ver "Cómo se construye", tanda 2: "avisos, directorio, mi perfil, invitar/compartir"). El documento no entra en detalle de estas 4 pantallas (su foco es el botón de pánico) -- el detalle de cada una se saca de la API ya construida en la Fase 1 y de su equivalente ya construido en la web (`comunicacion/`, `core/views.py::MiPerfilView`/`CompartirInvitacionView`/`DirectorioVecinosView`), citado en cada tarea.

## Global Constraints

- Backend: el único cambio es el agregado aditivo de la Tarea 1 (3 campos de solo lectura en la respuesta ya existente de `GET /api/v1/auth/me/`) -- no se toca nada más del lado Django/DRF, y el shape que ya consume `AuthContext` de la Tanda 1 (`rol`/`condominio`/`unidad`/`nombre`/`telefono`) sigue intacto.
- Todo endpoint nuevo que consume la app ya existe y ya está probado del lado del backend (Fase 1) -- esta tanda es 100% consumo + UI, salvo la Tarea 1.
- Una pantalla que depende del rol (delegado vs residente) lee `useAuth().membresia?.rol` -- nunca asume el rol a partir de la ausencia/presencia de otro campo.
- Todo `.then(...)` sobre una llamada a la API lleva su `.catch(...)` -- patrón ya establecido en la revisión final de la Tanda 1 (`alertas/index.tsx`, `alertas/[id].tsx`) para no dejar rechazos sin manejar.
- Ningún archivo de test se coloca dentro de `app_movil/src/app/` -- Expo Router los toma como rutas y rompe el bundle de producción (hallazgo real de la Tanda 1, confirmado con `npx expo start --web`). Van en `app_movil/src/__tests__/app/...` espejando la ruta, importando la pantalla real vía el alias `@/`.
- Toolchain ya aprendido en la Tanda 1, sigue aplicando: `render()` y `fireEvent`/`fireEvent.press` de `@testing-library/react-native` son `async`, siempre con `await`; `jest.advanceTimersByTimeAsync(ms)` en vez de `jest.advanceTimersByTime(ms)` cuando hay timers de por medio; `jest.useFakeTimers()` antes de `await render(...)` si el componente programa un timer al montar; `afterEach(async () => { await cleanup(); ... })` en todo archivo de test que renderice más de un componente, para que no se contaminen entre sí.
- Testing: cada paso de código entra con su test en rojo primero (TDD). Suite completa: `cd app_movil && npx jest --watchAll=false`.

## Review Focus

- Un residente (no delegado) abre Avisos -- no debe ver el botón/formulario de crear un aviso nuevo (eso es solo de delegado/devquad, `AvisoViewSet.get_permissions`); y si por un bug se llegara a mandar esa request, un 403 del backend no debe romper la pantalla.
- Un residente intenta llegar al Directorio (ej. un deep link directo) -- el backend lo rechaza con 403 (`EsDevquadODelegado`); la pantalla debe mostrar un mensaje razonable, no un rechazo sin manejar ni una pantalla en blanco.
- Falla la carga de "Mi perfil" (sin red, timeout) -- la pantalla no debe quedar en blanco para siempre, mismo patrón de `.catch` ya aplicado a las pantallas de alertas.
- El email que se intenta guardar en "Mi perfil" ya está en uso por otra cuenta -- el backend devuelve 400 con el mensaje real (`validate_email` de `MiPerfilSerializer`); la pantalla tiene que mostrar ESE mensaje, no uno genérico (requiere que `ErrorDeServidor` cargue el cuerpo de la respuesta, Tarea 2).
- Compartir la invitación falla o el usuario cancela la hoja de compartir nativa (puede pasar en Expo for Web, donde el soporte de Web Share varía por navegador) -- no debe romper la pantalla ni dejar un rechazo sin manejar.

---

## Nota sobre endpoints consumidos (ya existen, no se tocan salvo la Tarea 1)

| Acción | Método + ruta | Quién puede | Shape relevante |
|---|---|---|---|
| Mi perfil (ver) | `GET /api/v1/auth/me/` | Cualquier residente/delegado | Ver Tarea 1 -- shape ampliado |
| Mi perfil (editar) | `PATCH /api/v1/auth/me/` | Cualquier residente/delegado | `{first_name, last_name, email, telefono}` (los 4 opcionales, `partial=True`) → mismo shape de vuelta |
| Listar avisos | `GET /api/v1/avisos/` | Cualquier residente/delegado | lista de `AvisoOut` (ver abajo) |
| Marcar un aviso como leído | `POST /api/v1/avisos/<id>/marcar_leido/` | Cualquier residente/delegado | `AvisoOut` (acción pasiva -- ver Tarea 4) |
| Crear un aviso | `POST /api/v1/avisos/` `{titulo, cuerpo}` | Solo delegado (o devquad, fuera de esta app) | `AvisoOut` |
| Directorio | `GET /api/v1/directorio/` | Solo delegado (403 para residente) | lista de `{nombre, torre, unidad}` |
| Invitación/compartir | `GET /api/v1/invitacion/` | Cualquier residente/delegado | `{link_autoregistro, mensaje_whatsapp_invitacion}` |

```ts
type AvisoOut = {
  id: number;
  titulo: string;
  cuerpo: string;
  fecha_creacion: string;
  autor_nombre: string | null;
  torre_nombre: string | null;
  leido_por_count: number | null;    // null para residente/delegado -- solo devquad ve esto
  total_destinatarios: number | null;
};
```

**Por qué el marcado de "leído" es pasivo acá y no una acción explícita como en Alertas (D-05):** en `core/templates/core/inicio.html` (línea ~461), la web ya marca cada aviso como leído automáticamente apenas la lista se renderiza (`avisos.forEach(a => fetch(.../marcar_leido/))`) -- es informativo para devquad (cuántos vecinos vieron un aviso), no la base de una reaseguro personal durante una emergencia como en Alertas. La Tarea 4 replica ese mismo comportamiento, no inventa uno nuevo.

---

## File Structure

```
app_movil/src/
  api/
    auth.ts          (modificar -- MembresiaOut ampliado, agregar actualizarMiPerfil)
    client.ts         (modificar -- ErrorDeServidor carga el cuerpo de la respuesta)
    avisos.ts         (nuevo -- listarAvisos, marcarLeido, crearAviso)
    directorio.ts     (nuevo -- listarDirectorio)
    invitacion.ts     (nuevo -- obtenerInvitacion)
  app/(vecino)/
    _layout.tsx       (modificar -- 4 entradas nuevas al Drawer)
    perfil/index.tsx  (nuevo)
    avisos/index.tsx  (nuevo)
    directorio/index.tsx (nuevo)
    invitar/index.tsx (nuevo)
  __tests__/app/(vecino)/
    perfil/index.test.tsx
    avisos/index.test.tsx
    directorio/index.test.tsx
    invitar/index.test.tsx

core/
  api_views.py        (modificar -- MeView.get agrega first_name/last_name/email)
  tests.py            (agregar clase de test nueva al final)
```

---

### Task 1: Backend -- exponer nombre/apellido/email en `GET /api/v1/auth/me/`

**Files:**
- Modify: `core/api_views.py:59-67` (`MeView.get`)
- Test: `core/tests.py` (agregar al final, junto a `ApiMiPerfilYCambiarContrasenaTests` ya existente)

**Interfaces:**
- Produces: `GET /api/v1/auth/me/` ahora devuelve, además de `rol`/`condominio`/`unidad`/`nombre`/`telefono` (sin cambios), también `first_name`, `last_name`, `email` -- consumido por la Tarea 3 (pantalla de Mi Perfil) para pre-llenar el formulario de edición, que de otra forma no tiene de dónde sacar esos 3 campos por separado (`nombre` es el nombre completo ya concatenado).

- [ ] **Step 1: Escribir el test (falla primero)**

```python
def test_get_me_incluye_first_name_last_name_y_email(self):
    user = User.objects.create_user(
        username="perfil_test", first_name="Ana", last_name="Pérez", email="ana@test.cl",
    )
    Membresia.objects.create(user=user, condominio=self.condominio, rol="residente", terminos_aceptados_en=timezone.now())
    self.client.force_login(user)
    r = self.client.get(reverse("api-me"))
    datos = r.json()
    self.assertEqual(datos["first_name"], "Ana")
    self.assertEqual(datos["last_name"], "Pérez")
    self.assertEqual(datos["email"], "ana@test.cl")
```

Confirmar el nombre exacto de la clase de test existente donde agregarlo y los imports ya disponibles (`User`, `Membresia`, `timezone`, `reverse`) antes de escribir -- `core/tests.py` ya los usa en los tests de `telefono` de la Tanda 1.

- [ ] **Step 2: Correr, confirmar que falla**

Run: `./venv/Scripts/python.exe manage.py test core.tests -k test_get_me_incluye --keepdb -v 2`
Expected: FAIL -- `KeyError: 'first_name'` o similar (el campo no está en la respuesta todavía).

- [ ] **Step 3: Implementar**

En `MeView.get`, en vez de devolver `MembresiaSerializer(membresia).data` directo, armar el dict y agregarle los 3 campos del lado del `User`:

```python
datos = MembresiaSerializer(membresia).data
datos.update({
    "first_name": request.user.first_name,
    "last_name": request.user.last_name,
    "email": request.user.email,
})
return Response(datos)
```

- [ ] **Step 4: Correr, confirmar que pasa**

Run: `./venv/Scripts/python.exe manage.py test core.tests -k test_get_me_incluye --keepdb -v 2`
Expected: PASS

- [ ] **Step 5: Suite completa del backend + commit**

Run (en background, ~90-140s): `./venv/Scripts/python.exe manage.py test --keepdb`
Expected: todos los tests en verde (incluidos los 535+ ya existentes).

```bash
git add core/api_views.py core/tests.py
git commit -m "feat: GET /api/v1/auth/me/ incluye first_name/last_name/email"
git push
```

---

### Task 2: `ErrorDeServidor` carga el cuerpo de la respuesta

**Files:**
- Modify: `app_movil/src/api/client.ts` (clase `ErrorDeServidor`, función `apiFetch`)
- Modify: `app_movil/src/api/client.test.ts`

**Interfaces:**
- Consumes: nada nuevo.
- Produces: `ErrorDeServidor` gana una propiedad `body: unknown` (poblada con el JSON de la respuesta cuando se puede parsear, `undefined` si no) -- consumida por la Tarea 3 (mostrar el mensaje real de `validate_email` en vez de uno genérico).

- [ ] **Step 1: Escribir el test (falla primero)**

```ts
test("ErrorDeServidor carga el cuerpo de la respuesta (para mostrar mensajes de validación reales)", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue({ access: "acc1", refresh: "ref1" });
  global.fetch = jest.fn().mockResolvedValue({
    ok: false,
    status: 400,
    json: async () => ({ email: ["Ya existe otra cuenta con ese correo."] }),
  }) as any;
  try {
    await apiFetch("/api/v1/auth/me/", { method: "PATCH" });
    throw new Error("no debería llegar acá");
  } catch (error) {
    expect(error).toBeInstanceOf(ErrorDeServidor);
    expect((error as ErrorDeServidor).body).toEqual({ email: ["Ya existe otra cuenta con ese correo."] });
  }
});
```

- [ ] **Step 2: Correr, confirmar que falla**

Run: `cd app_movil && npx jest src/api/client.test.ts --watchAll=false`
Expected: FAIL -- `error.body` es `undefined`.

- [ ] **Step 3: Implementar**

`ErrorDeServidor` pasa a construirse con `new ErrorDeServidor(status, body)`; en los 2 lugares donde hoy se hace `throw new ErrorDeServidor(respuesta.status)` (requiereAuth=false y el flujo normal), parsear el cuerpo primero (`await respuesta.json().catch(() => undefined)`) y pasarlo como segundo argumento.

- [ ] **Step 4: Correr, confirmar que pasa**

Run: `cd app_movil && npx jest src/api/client.test.ts --watchAll=false`
Expected: PASS, y los tests ya existentes de `ErrorDeServidor` siguen pasando (no cambia su `status`, solo se agrega `body`).

- [ ] **Step 5: Suite completa + commit**

Run: `cd app_movil && npx jest --watchAll=false`
Expected: todos los tests en verde.

```bash
git add app_movil/src/api/client.ts app_movil/src/api/client.test.ts
git commit -m "feat: ErrorDeServidor carga el cuerpo de la respuesta"
git push
```

---

### Task 3: Mi perfil -- ver y editar

**Files:**
- Modify: `app_movil/src/api/auth.ts` (ampliar `MembresiaOut`, agregar `actualizarMiPerfil`)
- Create: `app_movil/src/app/(vecino)/perfil/index.tsx`
- Modify: `app_movil/src/app/(vecino)/_layout.tsx` (agregar `Drawer.Screen name="perfil/index"`)
- Create: `app_movil/src/__tests__/app/(vecino)/perfil/index.test.tsx`

**Interfaces:**
- Consumes: `apiFetch`, `ErrorDeServidor` (con `.body`, Tarea 2), `obtenerMiPerfil` (ya existe, Tanda 1), `useAuth()`.
- Produces: `actualizarMiPerfil(datos: {first_name?, last_name?, email?, telefono?}): Promise<{first_name, last_name, email, telefono}>` (`PATCH /api/v1/auth/me/`).

- [ ] **Step 1: Ampliar el tipo (sin test propio -- solo agrega campos opcionales, no cambia ningún consumidor existente)**

En `api/auth.ts`, `MembresiaOut` gana `first_name?: string`, `last_name?: string`, `email?: string`.

- [ ] **Step 2: Escribir el test de `actualizarMiPerfil` (falla primero)**

```ts
// en api/auth.test.ts (nuevo archivo, o agregado si ya existiera)
test("actualizarMiPerfil hace PATCH a /auth/me/ con los campos dados", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ first_name: "Ana", last_name: "P", email: "a@test.cl", telefono: "123" });
  const resultado = await actualizarMiPerfil({ first_name: "Ana", telefono: "123" });
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/auth/me/", {
    method: "PATCH",
    body: JSON.stringify({ first_name: "Ana", telefono: "123" }),
  });
  expect(resultado.first_name).toBe("Ana");
});
```

(mockear `./client` con `jest.mock("./client")`, mismo patrón que `api/alertas.test.ts`).

- [ ] **Step 3: Correr, confirmar que falla**

Run: `cd app_movil && npx jest src/api/auth.test.ts --watchAll=false`
Expected: FAIL -- `actualizarMiPerfil` no existe.

- [ ] **Step 4: Implementar `actualizarMiPerfil`**

- [ ] **Step 5: Correr, confirmar que pasa**

Run: `cd app_movil && npx jest src/api/auth.test.ts --watchAll=false`
Expected: PASS

- [ ] **Step 6: Escribir los tests de la pantalla (fallan primero)**

```tsx
// src/__tests__/app/(vecino)/perfil/index.test.tsx
jest.mock("@/auth/AuthContext", () => ({
  useAuth: () => ({ membresia: { rol: "residente" } }),
}));

import { render, fireEvent, screen } from "@testing-library/react-native";
import PantallaPerfil from "@/app/(vecino)/perfil/index";
import * as authApi from "@/api/auth";
import { ErrorDeRed, ErrorDeServidor } from "@/api/client";

afterEach(() => jest.restoreAllMocks());

test("al montar, carga el perfil y pre-llena el formulario", async () => {
  jest.spyOn(authApi, "obtenerMiPerfil").mockResolvedValue({
    rol: "residente", condominio: { id: 1, nombre: "X" }, unidad: null,
    nombre: "Ana Pérez", telefono: "123", first_name: "Ana", last_name: "Pérez", email: "ana@test.cl",
  });
  await render(<PantallaPerfil />);
  await screen.findByDisplayValue("Ana");
  expect(screen.getByDisplayValue("ana@test.cl")).toBeTruthy();
});

test("si falla la carga del perfil, muestra un error en vez de quedar en blanco", async () => {
  jest.spyOn(authApi, "obtenerMiPerfil").mockRejectedValue(new ErrorDeRed("sin red"));
  await render(<PantallaPerfil />);
  await screen.findByText(/no se pudo cargar tu perfil/i);
});

test("si el email ya está en uso, muestra el mensaje real del backend", async () => {
  jest.spyOn(authApi, "obtenerMiPerfil").mockResolvedValue({
    rol: "residente", condominio: { id: 1, nombre: "X" }, unidad: null,
    nombre: "Ana Pérez", telefono: "", first_name: "Ana", last_name: "Pérez", email: "ana@test.cl",
  });
  jest.spyOn(authApi, "actualizarMiPerfil").mockRejectedValue(
    new ErrorDeServidor(400, { email: ["Ya existe otra cuenta con ese correo."] })
  );
  await render(<PantallaPerfil />);
  await screen.findByDisplayValue("Ana");
  await fireEvent.press(screen.getByText(/guardar/i));
  await screen.findByText(/ya existe otra cuenta con ese correo/i);
});
```

- [ ] **Step 7: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest "src/__tests__/app/\(vecino\)/perfil" --watchAll=false`
Expected: FAIL -- la pantalla no existe.

- [ ] **Step 8: Implementar la pantalla**

Formulario controlado (`useState` por campo), carga inicial vía `useEffect` + `obtenerMiPerfil().then(...).catch(() => setError("No se pudo cargar tu perfil."))`. Al guardar, llama `actualizarMiPerfil`; si rechaza con `ErrorDeServidor`, lee `error.body?.email?.[0]` (o el primer mensaje que venga, el shape de DRF es `{campo: [mensajes]}`) y lo muestra; si no hay `body` legible, un mensaje genérico de respaldo. Campo `telefono` reutiliza el mismo patrón de validación del backend (no hace falta replicarla en el cliente, el backend ya la aplica).

- [ ] **Step 9: Correr, confirmar que pasan**

Run: `cd app_movil && npx jest "src/__tests__/app/\(vecino\)/perfil" --watchAll=false`
Expected: PASS

- [ ] **Step 10: Agregar al Drawer**

En `(vecino)/_layout.tsx`, agregar `<Drawer.Screen name="perfil/index" options={{ title: "Mi perfil" }} />`.

- [ ] **Step 11: Suite completa + verificación manual + commit**

Run: `cd app_movil && npx jest --watchAll=false`
Expected: todos los tests en verde.

Run: `cd app_movil && npx expo start --web` (manual, confirmar que `/perfil` sirve sin error, luego detener el servidor).

```bash
git add app_movil/src/api/auth.ts app_movil/src/api/auth.test.ts app_movil/src/app/\(vecino\)/perfil app_movil/src/app/\(vecino\)/_layout.tsx app_movil/src/__tests__/app/\(vecino\)/perfil
git commit -m "feat: pantalla de Mi perfil (ver y editar)"
git push
```

---

### Task 4: Avisos -- listar (con marcado pasivo) y crear (solo delegado)

**Files:**
- Create: `app_movil/src/api/avisos.ts`
- Create: `app_movil/src/app/(vecino)/avisos/index.tsx`
- Modify: `app_movil/src/app/(vecino)/_layout.tsx` (agregar `Drawer.Screen name="avisos/index"`)
- Create: `app_movil/src/__tests__/app/(vecino)/avisos/index.test.tsx`

**Interfaces:**
- Consumes: `apiFetch`, `useAuth()` (para `membresia?.rol`).
- Produces: `listarAvisos(): Promise<AvisoOut[]>`, `marcarLeido(id: number): Promise<AvisoOut>`, `crearAviso(payload: {titulo: string; cuerpo: string}): Promise<AvisoOut>` en `api/avisos.ts`.

- [ ] **Step 1: Escribir los tests de `api/avisos.ts` (fallan primero)**

```ts
// api/avisos.test.ts
jest.mock("./client");
import { listarAvisos, marcarLeido, crearAviso } from "./avisos";
import { apiFetch } from "./client";

test("listarAvisos pide /api/v1/avisos/", async () => {
  (apiFetch as jest.Mock).mockResolvedValue([]);
  await listarAvisos();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/avisos/");
});

test("marcarLeido pega al endpoint correcto", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ id: 1 });
  await marcarLeido(1);
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/avisos/1/marcar_leido/", { method: "POST" });
});

test("crearAviso manda titulo y cuerpo", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ id: 2 });
  await crearAviso({ titulo: "Corte de agua", cuerpo: "Mañana 9-12h" });
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/avisos/", {
    method: "POST",
    body: JSON.stringify({ titulo: "Corte de agua", cuerpo: "Mañana 9-12h" }),
  });
});
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest src/api/avisos.test.ts --watchAll=false`
Expected: FAIL -- `avisos.ts` no existe.

- [ ] **Step 3: Implementar `api/avisos.ts`**

`AvisoOut` con el shape de la tabla de endpoints de este plan.

- [ ] **Step 4: Correr, confirmar que pasan**

Run: `cd app_movil && npx jest src/api/avisos.test.ts --watchAll=false`
Expected: PASS

- [ ] **Step 5: Escribir los tests de la pantalla (fallan primero)**

```tsx
// src/__tests__/app/(vecino)/avisos/index.test.tsx
import { render, screen } from "@testing-library/react-native";
import ListaAvisosScreen from "@/app/(vecino)/avisos/index";
import * as avisosApi from "@/api/avisos";
import { ErrorDeRed } from "@/api/client";

jest.mock("@/auth/AuthContext", () => ({ useAuth: () => ({ membresia: { rol: "residente" } }) }));

afterEach(() => jest.restoreAllMocks());

test("al listar, marca cada aviso como leido de forma pasiva (mismo comportamiento que la web)", async () => {
  jest.spyOn(avisosApi, "listarAvisos").mockResolvedValue([
    { id: 1, titulo: "A", cuerpo: "...", fecha_creacion: "2026-01-01T00:00:00Z", autor_nombre: null, torre_nombre: null, leido_por_count: null, total_destinatarios: null },
  ] as any);
  const marcarSpy = jest.spyOn(avisosApi, "marcarLeido").mockResolvedValue({} as any);
  await render(<ListaAvisosScreen />);
  await screen.findByText("A");
  expect(marcarSpy).toHaveBeenCalledWith(1);
});

test("un residente (no delegado) no ve el formulario de crear aviso", async () => {
  jest.spyOn(avisosApi, "listarAvisos").mockResolvedValue([]);
  await render(<ListaAvisosScreen />);
  expect(screen.queryByText(/publicar aviso/i)).toBeNull();
});

test("si falla la carga, muestra un error en vez de un rechazo sin manejar", async () => {
  jest.spyOn(avisosApi, "listarAvisos").mockRejectedValue(new ErrorDeRed("sin red"));
  await render(<ListaAvisosScreen />);
  await screen.findByText(/no se pudieron cargar los avisos/i);
});
```

- [ ] **Step 6: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest "src/__tests__/app/\(vecino\)/avisos" --watchAll=false`
Expected: FAIL

- [ ] **Step 7: Implementar la pantalla**

Al montar: `listarAvisos().then(lista => { setAvisos(lista); lista.forEach(a => marcarLeido(a.id).catch(() => {})); }).catch(...)` -- el `marcarLeido` de cada uno también lleva su propio `.catch` silencioso (si falla marcar uno como leído, no debe romper la lista ya mostrada). El formulario de "Publicar aviso" (`titulo`+`cuerpo`+botón) solo se renderiza si `useAuth().membresia?.rol === "delegado"`.

- [ ] **Step 8: Escribir el test del formulario de delegado (falla primero)**

```tsx
// agregar a src/__tests__/app/(vecino)/avisos/index.test.tsx, con un segundo jest.mock para membresia delegado
```

Nota para quien implemente: como `jest.mock("@/auth/AuthContext", ...)` ya está fijado arriba del archivo con `rol: "residente"`, el caso de delegado necesita su propio archivo de test (`index.delegado.test.tsx` en la misma carpeta, con su propio `jest.mock` apuntando a `rol: "delegado"`) -- `jest.mock` de módulo no se puede cambiar a mitad de archivo de forma confiable entre tests.

```tsx
// src/__tests__/app/(vecino)/avisos/index.delegado.test.tsx
jest.mock("@/auth/AuthContext", () => ({ useAuth: () => ({ membresia: { rol: "delegado" } }) }));

import { render, fireEvent, screen } from "@testing-library/react-native";
import ListaAvisosScreen from "@/app/(vecino)/avisos/index";
import * as avisosApi from "@/api/avisos";

afterEach(() => jest.restoreAllMocks());

test("un delegado ve el formulario y puede publicar un aviso", async () => {
  jest.spyOn(avisosApi, "listarAvisos").mockResolvedValue([]);
  const crearSpy = jest.spyOn(avisosApi, "crearAviso").mockResolvedValue({ id: 9 } as any);
  await render(<ListaAvisosScreen />);
  await screen.findByText(/publicar aviso/i);
  fireEvent.changeText(screen.getByPlaceholderText(/título/i), "Corte de agua");
  fireEvent.changeText(screen.getByPlaceholderText(/mensaje/i), "Mañana 9-12h");
  await fireEvent.press(screen.getByText(/publicar aviso/i));
  expect(crearSpy).toHaveBeenCalledWith({ titulo: "Corte de agua", cuerpo: "Mañana 9-12h" });
});
```

- [ ] **Step 9: Correr, confirmar que fallan (archivo nuevo + lo que falte de Step 7)**

Run: `cd app_movil && npx jest "src/__tests__/app/\(vecino\)/avisos" --watchAll=false`

- [ ] **Step 10: Terminar la implementación (formulario de delegado)**

- [ ] **Step 11: Correr, confirmar que pasan**

Run: `cd app_movil && npx jest "src/__tests__/app/\(vecino\)/avisos" --watchAll=false`
Expected: PASS

- [ ] **Step 12: Agregar al Drawer**

`<Drawer.Screen name="avisos/index" options={{ title: "Avisos" }} />`.

- [ ] **Step 13: Suite completa + verificación manual + commit**

Run: `cd app_movil && npx jest --watchAll=false`

Run: `cd app_movil && npx expo start --web` (manual, `/avisos` sin error, detener el servidor).

```bash
git add app_movil/src/api/avisos.ts app_movil/src/api/avisos.test.ts app_movil/src/app/\(vecino\)/avisos app_movil/src/app/\(vecino\)/_layout.tsx app_movil/src/__tests__/app/\(vecino\)/avisos
git commit -m "feat: avisos -- listar con marcado pasivo y publicar (solo delegado)"
git push
```

---

### Task 5: Directorio -- listar (solo delegado)

**Files:**
- Create: `app_movil/src/api/directorio.ts`
- Create: `app_movil/src/app/(vecino)/directorio/index.tsx`
- Modify: `app_movil/src/app/(vecino)/_layout.tsx` (agregar `Drawer.Screen name="directorio/index"`, oculto si no es delegado)

**Interfaces:**
- Consumes: `apiFetch`, `useAuth()`.
- Produces: `listarDirectorio(): Promise<{nombre: string; torre: string | null; unidad: string | null}[]>`.

- [ ] **Step 1: Escribir el test de `api/directorio.ts` (falla primero)**

```ts
jest.mock("./client");
import { listarDirectorio } from "./directorio";
import { apiFetch } from "./client";

test("listarDirectorio pide /api/v1/directorio/", async () => {
  (apiFetch as jest.Mock).mockResolvedValue([]);
  await listarDirectorio();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/directorio/");
});
```

- [ ] **Step 2: Correr, confirmar que falla**

Run: `cd app_movil && npx jest src/api/directorio.test.ts --watchAll=false`

- [ ] **Step 3: Implementar `api/directorio.ts`**

- [ ] **Step 4: Correr, confirmar que pasa**

- [ ] **Step 5: Escribir los tests de la pantalla (fallan primero)**

```tsx
jest.mock("@/auth/AuthContext", () => ({ useAuth: () => ({ membresia: { rol: "delegado" } }) }));

import { render, screen } from "@testing-library/react-native";
import DirectorioScreen from "@/app/(vecino)/directorio/index";
import * as directorioApi from "@/api/directorio";
import { ErrorDeRed, ErrorDeServidor } from "@/api/client";

afterEach(() => jest.restoreAllMocks());

test("lista nombre y unidad de cada miembro", async () => {
  jest.spyOn(directorioApi, "listarDirectorio").mockResolvedValue([
    { nombre: "Ana Pérez", torre: "A", unidad: "101" },
  ]);
  await render(<DirectorioScreen />);
  await screen.findByText("Ana Pérez");
});

test("si el backend rechaza con 403 (residente, por deep link), muestra un mensaje en vez de romper", async () => {
  jest.spyOn(directorioApi, "listarDirectorio").mockRejectedValue(new ErrorDeServidor(403));
  await render(<DirectorioScreen />);
  await screen.findByText(/no tienes acceso al directorio/i);
});

test("si falla por red, muestra un error en vez de un rechazo sin manejar", async () => {
  jest.spyOn(directorioApi, "listarDirectorio").mockRejectedValue(new ErrorDeRed("sin red"));
  await render(<DirectorioScreen />);
  await screen.findByText(/no se pudo cargar el directorio/i);
});
```

- [ ] **Step 6: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest "src/__tests__/app/\(vecino\)/directorio" --watchAll=false`

- [ ] **Step 7: Implementar la pantalla**

Distinguir el mensaje de 403 (`error instanceof ErrorDeServidor && error.status === 403`) del resto, con los 2 textos exactos de los tests.

- [ ] **Step 8: Correr, confirmar que pasan**

- [ ] **Step 9: Agregar al Drawer, oculto para residente**

```tsx
<Drawer.Screen
  name="directorio/index"
  options={{ title: "Directorio", drawerItemStyle: membresia?.rol !== "delegado" ? { display: "none" } : undefined }}
/>
```

`VecinoLayout` (`(vecino)/_layout.tsx`) hoy no importa `useAuth` -- agregar `import { useAuth } from "@/auth/AuthContext";` y `const { membresia } = useAuth();` dentro del componente.

- [ ] **Step 10: Suite completa + verificación manual + commit**

Run: `cd app_movil && npx jest --watchAll=false`

Run: `cd app_movil && npx expo start --web` (manual, `/directorio` sin error, detener el servidor).

```bash
git add app_movil/src/api/directorio.ts app_movil/src/api/directorio.test.ts app_movil/src/app/\(vecino\)/directorio app_movil/src/app/\(vecino\)/_layout.tsx app_movil/src/__tests__/app/\(vecino\)/directorio
git commit -m "feat: directorio -- listar (solo delegado, oculto para residente)"
git push
```

---

### Task 6: Invitar/compartir

**Files:**
- Create: `app_movil/src/api/invitacion.ts`
- Create: `app_movil/src/app/(vecino)/invitar/index.tsx`
- Modify: `app_movil/src/app/(vecino)/_layout.tsx` (agregar `Drawer.Screen name="invitar/index"`)

**Interfaces:**
- Consumes: `apiFetch`, `Share` de `react-native` (ya incluido, sin instalar nada nuevo).
- Produces: `obtenerInvitacion(): Promise<{link_autoregistro: string; mensaje_whatsapp_invitacion: string}>`.

- [ ] **Step 1: Escribir el test de `api/invitacion.ts` (falla primero)**

```ts
jest.mock("./client");
import { obtenerInvitacion } from "./invitacion";
import { apiFetch } from "./client";

test("obtenerInvitacion pide /api/v1/invitacion/", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ link_autoregistro: "https://...", mensaje_whatsapp_invitacion: "..." });
  await obtenerInvitacion();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/invitacion/");
});
```

- [ ] **Step 2: Correr, confirmar que falla**

Run: `cd app_movil && npx jest src/api/invitacion.test.ts --watchAll=false`

- [ ] **Step 3: Implementar `api/invitacion.ts`**

- [ ] **Step 4: Correr, confirmar que pasa**

- [ ] **Step 5: Escribir los tests de la pantalla (fallan primero)**

```tsx
import { render, fireEvent, screen } from "@testing-library/react-native";
import { Share } from "react-native";
import InvitarScreen from "@/app/(vecino)/invitar/index";
import * as invitacionApi from "@/api/invitacion";
import { ErrorDeRed } from "@/api/client";

afterEach(() => jest.restoreAllMocks());

test("al tocar Compartir, abre la hoja de compartir nativa con el mensaje", async () => {
  jest.spyOn(invitacionApi, "obtenerInvitacion").mockResolvedValue({
    link_autoregistro: "https://x/registro/abc", mensaje_whatsapp_invitacion: "Te invito a...",
  });
  const shareSpy = jest.spyOn(Share, "share").mockResolvedValue({ action: Share.sharedAction } as any);
  await render(<InvitarScreen />);
  await screen.findByText(/compartir/i);
  await fireEvent.press(screen.getByText(/compartir/i));
  expect(shareSpy).toHaveBeenCalledWith({ message: "Te invito a..." });
});

test("si Share.share rechaza (ej. cancelado), no rompe la pantalla", async () => {
  jest.spyOn(invitacionApi, "obtenerInvitacion").mockResolvedValue({
    link_autoregistro: "https://x", mensaje_whatsapp_invitacion: "Te invito a...",
  });
  jest.spyOn(Share, "share").mockRejectedValue(new Error("cancelado"));
  await render(<InvitarScreen />);
  await fireEvent.press(await screen.findByText(/compartir/i));
  await screen.findByText(/compartir/i); // la pantalla sigue en pie, no se rompió
});

test("si falla obtener la invitacion, muestra un error", async () => {
  jest.spyOn(invitacionApi, "obtenerInvitacion").mockRejectedValue(new ErrorDeRed("sin red"));
  await render(<InvitarScreen />);
  await screen.findByText(/no se pudo cargar la invitación/i);
});
```

- [ ] **Step 6: Correr, confirmar que fallan**

Run: `cd app_movil && npx jest "src/__tests__/app/\(vecino\)/invitar" --watchAll=false`

- [ ] **Step 7: Implementar la pantalla**

`Share.share({ message: mensaje_whatsapp_invitacion })` dentro de un `try/catch` silencioso (cancelar la hoja de compartir no es un error que haya que mostrarle a nadie).

- [ ] **Step 8: Correr, confirmar que pasan**

- [ ] **Step 9: Agregar al Drawer**

`<Drawer.Screen name="invitar/index" options={{ title: "Invitar vecinos" }} />`.

- [ ] **Step 10: Suite completa + verificación manual + commit**

Run: `cd app_movil && npx jest --watchAll=false`

Run: `cd app_movil && npx expo start --web` (manual, `/invitar` sin error, detener el servidor).

```bash
git add app_movil/src/api/invitacion.ts app_movil/src/api/invitacion.test.ts app_movil/src/app/\(vecino\)/invitar app_movil/src/app/\(vecino\)/_layout.tsx app_movil/src/__tests__/app/\(vecino\)/invitar
git commit -m "feat: invitar/compartir -- hoja de compartir nativa"
git push
```

---

## Self-Review (hecho al escribir este plan)

**Cobertura del spec:** las 4 pantallas de "Lo demás del vecino" (avisos, directorio, mi perfil, invitar/compartir) tienen tarea propia. El agregado de email/first_name/last_name (Tarea 1) y el body de `ErrorDeServidor` (Tarea 2) son prerrequisitos descubiertos al diseñar el plan (el spec no los menciona porque no entra en detalle de estas pantallas), documentados con su propio porqué.

**Review Focus:** los 5 puntos tienen test propio -- residente no ve el formulario de avisos (Tarea 4), residente rechazado del directorio con 403 manejado (Tarea 5), perfil no queda en blanco ante un error de red (Tarea 3), mensaje real de email duplicado (Tarea 3, vía Tarea 2), `Share.share()` cancelado/rechazado no rompe la pantalla (Tarea 6).

**Consistencia de tipos:** `AvisoOut` se fija una sola vez (tabla de endpoints) y se reusa igual en la Tarea 4. `MembresiaOut` se amplía (no se reemplaza) en la Tarea 3, así que el `AuthContext` de la Tanda 1 sigue compilando sin cambios.

**Proporción:** 6 tareas -- 2 prerrequisitos chicos (backend + cliente) y 4 pantallas, cada una del mismo tamaño que las ya construidas en la Tanda 1.

## Qué queda a criterio de quien lo construya

- Diseño visual exacto de cada pantalla (el plan fija el comportamiento y los textos que los tests necesitan, no el detalle pixel a pixel) -- reusar `colores` de `theme/colores.ts`, mismo criterio que toda la Tanda 1.
- Si "Mi perfil" valida el formato de email del lado del cliente antes de mandarlo, o deja que el backend sea la única fuente de verdad (ambos cumplen el Review Focus, que exige mostrar el mensaje del backend cuando llega).
- Orden de las 4 entradas nuevas en el Drawer -- no es crítico, el plan no lo fija.
- Tandas 3 (modo administrador) y 4 (pagos/foto/modo silencioso) de la Fase 2, y la Fase 3 (panel institucional), quedan para planes aparte, después de esta.

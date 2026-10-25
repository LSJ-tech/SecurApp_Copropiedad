# Pantalla principal del móvil: mezclar el pánico con el contenido de la web Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> para implementar este plan tarea por tarea (decidido con el usuario, mismo
> método que los dos planes anteriores de esta sesión). Steps use checkbox
> (`- [ ]`) syntax for tracking.

**Goal:** Rediseñar la pantalla principal de la app móvil (rol residente/
delegado) para que, debajo de una franja de pánico fija y compacta (en vez
del círculo gigante actual), muestre el mismo contenido que ya existe en la
web: donación, mi depto, invitar vecinos (+ directorio si es delegado), y
alertas activas.

**Architecture:** Dos campos nuevos en serializers ya existentes del
backend (sin endpoints nuevos) para que `/api/v1/auth/me/` traiga las
etiquetas del condominio y el nombre de la torre; del lado móvil, un
cambio de estilo puro en `BotonPanico` y una reestructuración de
`(vecino)/index.tsx` que reusa clientes de API ya construidos
(donaciones, alertas, auth) -- ningún endpoint nuevo del lado móvil.

**Tech Stack:** Django 6.1 + DRF (backend), Expo/React Native + Jest/RTL
(mobile), mismos patrones ya usados en el proyecto.

**Spec:** `docs/superpowers/specs/2026-10-25-app-movil-home-unificado-design.md`

## Global Constraints

- TDD obligatorio: cada paso de test se escribe y se corre en rojo antes
  del código que lo hace pasar.
- Suite completa en verde antes de cada commit (backend:
  `./venv/Scripts/python.exe manage.py test`; mobile: `npm test` dentro de
  `app_movil/`).
- El mecanismo de pánico (`BotonPanico.tsx`, `SelectorTipoAlerta.tsx`,
  `enviarAlerta.ts`, GPS, cola de reintento, ventana de cancelar, la
  guarda `enviandoRef` contra doble envío) es código ya revisado y en
  producción -- este trabajo NO le toca la lógica, solo el estilo visual
  del contenedor del botón.
- Nada de la web se toca -- `core/templates/core/inicio.html` sigue
  exactamente igual.
- Ningún mecanismo de pánico se unifica entre plataformas -- cada una
  mantiene el suyo (decisión explícita del usuario).
- Sin estadísticas de Blocks/Departamentos/Vecinos -- descartadas a
  propósito para esta pantalla.
- Mobile: `jest.restoreAllMocks()` no limpia el historial de llamadas de
  un `jest.fn()` que no es un spy de verdad (ej. un mock de hook
  reconfigurado con `.mockReturnValue()` en cada test) -- agregar
  `jest.clearAllMocks()` en `afterEach` para esos casos (mismo patrón ya
  documentado en este proyecto).

## Review Focus

- Un residente sin `unidad` asignada no debe romper la tarjeta "Mi
  depto" ni mostrar "undefined" -- debe mostrar el mismo mensaje que ya
  usa la web, con el género correcto -- cubierto en Task 3.
- El botón de pánico tiene que seguir funcionando aunque fallen las
  tarjetas nuevas (donación, alertas activas) -- no puede depender de
  ellas para disparar una alerta real -- cubierto en Task 3.
- "Directorio" no debe aparecer para un residente común (sigue siendo
  solo para delegado, mismo criterio que ya usa el Drawer) -- cubierto
  en Task 3.
- Una unidad con `torre=None` no debe romper el campo nuevo `torre_nombre`
  de la API (NULL en una FK, no un string vacío) -- cubierto en Task 1.
- Que el botón de pánico siga disparando exactamente igual (mismo
  mecanismo de 2s, mismo testID, mismas guardas) tras el cambio de
  estilo -- cubierto reutilizando los tests ya existentes de
  `BotonPanico.test.tsx` y `(vecino)/index.test.tsx` como regresión en
  Tasks 2 y 3.

---

### Task 1: Backend -- etiquetas del condominio y torre de la unidad en `/api/v1/auth/me/`

**Files:**
- Modify: `core/serializers.py` (`CondominioResumenSerializer`,
  `UnidadResumenSerializer`)
- Test: `core/tests.py` (clase `ApiAuthTests`, agregar 2 tests)

**Interfaces:**
- Produces: `GET /api/v1/auth/me/` (`reverse("api-me")`) ahora incluye
  `condominio.etiqueta_torre`, `condominio.etiqueta_unidad`,
  `condominio.genero_unidad` (strings), y `unidad.torre_nombre` (string o
  `null` si la unidad no tiene torre).

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a la clase `ApiAuthTests` en `core/tests.py`, después de
`test_me_sin_membresia_devuelve_409` (línea ~1018):

```python
def test_me_incluye_las_etiquetas_del_condominio_y_la_torre_de_la_unidad(self):
    self.condominio.etiqueta_torre = "Block"
    self.condominio.etiqueta_unidad = "Departamento"
    self.condominio.genero_unidad = "m"
    self.condominio.save()
    torre = Torre.objects.create(condominio=self.condominio, nombre="9")
    unidad = Unidad.objects.create(condominio=self.condominio, torre=torre, numero="54")
    self.membresia.unidad = unidad
    self.membresia.save()
    login = self.client.post(reverse("api-login"), {"username": "api_auth_user", "password": "clave-segura-123"})
    access = login.json()["access"]
    r = self.client.get(reverse("api-me"), HTTP_AUTHORIZATION=f"Bearer {access}")
    self.assertEqual(r.status_code, 200)
    datos = r.json()
    self.assertEqual(datos["condominio"]["etiqueta_torre"], "Block")
    self.assertEqual(datos["condominio"]["etiqueta_unidad"], "Departamento")
    self.assertEqual(datos["condominio"]["genero_unidad"], "m")
    self.assertEqual(datos["unidad"]["torre_nombre"], "9")

def test_me_unidad_sin_torre_trae_torre_nombre_none(self):
    unidad = Unidad.objects.create(condominio=self.condominio, numero="12")
    self.membresia.unidad = unidad
    self.membresia.save()
    login = self.client.post(reverse("api-login"), {"username": "api_auth_user", "password": "clave-segura-123"})
    access = login.json()["access"]
    r = self.client.get(reverse("api-me"), HTTP_AUTHORIZATION=f"Bearer {access}")
    self.assertIsNone(r.json()["unidad"]["torre_nombre"])
```

- [ ] **Step 2: Correr los tests para confirmar que fallan**

Run: `./venv/Scripts/python.exe manage.py test core.tests.ApiAuthTests.test_me_incluye_las_etiquetas_del_condominio_y_la_torre_de_la_unidad core.tests.ApiAuthTests.test_me_unidad_sin_torre_trae_torre_nombre_none -v 2`
Expected: FAIL -- `KeyError: 'etiqueta_torre'` (el campo todavía no existe en la respuesta).

- [ ] **Step 3: Agregar los campos a `CondominioResumenSerializer` y `UnidadResumenSerializer` en `core/serializers.py`**

```python
class CondominioResumenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Condominio
        fields = ["id", "nombre", "plan", "puede_operar", "etiqueta_torre", "etiqueta_unidad", "genero_unidad"]


class UnidadResumenSerializer(serializers.ModelSerializer):
    torre_nombre = serializers.CharField(source="torre.nombre", read_only=True, default=None)

    class Meta:
        model = Unidad
        fields = ["id", "numero", "torre_nombre"]
```

(Mismo patrón dotted-source + `default=None` que ya usan
`MembresiaListSerializer.unidad_torre` y `AlertaSerializer.autor_torre`
en este mismo archivo -- probado contra una FK `torre` nula.)

- [ ] **Step 4: Correr los tests para confirmar que pasan**

Run: `./venv/Scripts/python.exe manage.py test core.tests.ApiAuthTests -v 2`
Expected: PASS (todos los de la clase, incluidos los 2 nuevos).

- [ ] **Step 5: Correr la suite completa**

Run: `./venv/Scripts/python.exe manage.py test`
Expected: PASS, sin regresiones.

- [ ] **Step 6: Commit**

```bash
git add core/serializers.py core/tests.py
git commit -m "feat(api): incluir etiquetas del condominio y torre de la unidad en /auth/me/"
```

---

### Task 2: Mobile -- franja de pánico fija (restyle de `BotonPanico`)

**Files:**
- Modify: `app_movil/src/components/BotonPanico.tsx` (solo `styles`)

**Interfaces:**
- Consumes: nada nuevo.
- Produces: `BotonPanico` sigue exportando exactamente los mismos props
  (`onConfirmar`, `tipoSeleccionado`) y el mismo `testID="boton-panico"`
  -- Task 3 lo sigue usando igual.

- [ ] **Step 1: Cambiar `styles.boton`/`styles.texto` en `BotonPanico.tsx`**

Cambio puro de estilo, sin tocar `manejarPressIn`/`manejarPressOut` ni el
JSX del `Pressable`/`Text`: de círculo de 220x220 centrado, a una franja
de ancho completo (`width: "100%"`), fija (sin `position: fixed` --
alcanza con que viva fuera del `ScrollView` que arma Task 3), roja
(mismo rojo que ya usa el proyecto para estados de error/peligro,
`#b00020`, en vez de `colores.primary`), con el mismo texto "Mantén
presionado 2 segundos". No hace falta un test nuevo -- es un cambio sin
comportamiento nuevo, lo prueba el paso siguiente.

- [ ] **Step 2: Correr los tests existentes para confirmar que el comportamiento no cambió**

Run: `npm test -- BotonPanico.test.tsx` (dentro de `app_movil/`)
Expected: PASS (3/3, los mismos tests de siempre).

- [ ] **Step 3: Commit**

```bash
git add app_movil/src/components/BotonPanico.tsx
git commit -m "feat(mobile): franja de pánico fija en vez del círculo grande"
```

---

### Task 3: Mobile -- reestructurar la pantalla principal con las tarjetas de la web

**Files:**
- Modify: `app_movil/src/app/(vecino)/index.tsx`
- Modify: `app_movil/src/api/auth.ts` (tipo `MembresiaOut`)
- Modify: `app_movil/src/__tests__/app/(vecino)/index.test.tsx`

**Interfaces:**
- Consumes: `BotonPanico`/`SelectorTipoAlerta`/`VentanaCancelar`/
  `enviarAlerta`/`obtenerUbicacionActual` (ya existen, sin cambios de
  interfaz); `useAuth()` de `@/auth/AuthContext` (ya existe, expone
  `membresia: MembresiaOut | null`); `obtenerMiDonacion()` de
  `@/api/donaciones` (ya existe, `Promise<MiDonacion>`); `listarAlertas`
  de `@/api/alertas` (ya existe, `listarAlertas("activa"): Promise<AlertaOut[]>`);
  los campos nuevos de Task 1 (`condominio.etiqueta_torre`/
  `etiqueta_unidad`/`genero_unidad`, `unidad.torre_nombre`).

- [ ] **Step 1: Extender el tipo `MembresiaOut` en `app_movil/src/api/auth.ts`**

```typescript
export type MembresiaOut = {
  rol: string;
  condominio: { id: number; nombre: string; etiqueta_torre: string; etiqueta_unidad: string; genero_unidad: string; [k: string]: unknown };
  unidad: { numero: string; torre_nombre: string | null; [k: string]: unknown } | null;
  nombre: string;
  telefono: string;
  first_name?: string;
  last_name?: string;
  email?: string;
};
```

- [ ] **Step 2: Escribir los tests que fallan**

En `app_movil/src/__tests__/app/(vecino)/index.test.tsx`, agregar el
mock de router/auth/APIs arriba de los imports existentes y un
`beforeEach` con valores por defecto (así los 3 tests que ya existen
siguen pasando sin tocar su cuerpo):

```typescript
const mockPush = jest.fn();
jest.mock("expo-router", () => ({
  useRouter: () => ({ push: mockPush }),
}));

const mockUseAuth = jest.fn();
jest.mock("@/auth/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

// ...(imports existentes, más:)
import * as donacionesApi from "@/api/donaciones";
import * as alertasApi from "@/api/alertas";

beforeEach(() => {
  mockUseAuth.mockReturnValue({
    membresia: {
      rol: "residente",
      condominio: { id: 1, nombre: "Empart", etiqueta_torre: "Block", etiqueta_unidad: "Departamento", genero_unidad: "m" },
      unidad: null,
      nombre: "Logan", telefono: "",
    },
  });
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({
    donacion_actual: null, pagos: [], total_donado: "0.00", cantidad_aportes: 0,
  });
  jest.spyOn(alertasApi, "listarAlertas").mockResolvedValue([]);
});

afterEach(() => {
  // (sumar a los afterEach ya existentes del archivo, no reemplazarlos)
  jest.clearAllMocks();
});
```

Tests nuevos (agregar al final del archivo):

```typescript
test("con donación activa, la tarjeta muestra el monto mensual y el botón navega a Donar", async () => {
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({
    donacion_actual: { estado: "autorizada", monto: "2000.00", fecha_creacion: "2026-09-01T00:00:00Z" },
    pagos: [], total_donado: "2000.00", cantidad_aportes: 1,
  });
  await render(<PantallaPanico />);
  await screen.findByText(/2\.000\/mes/);
  await fireEvent.press(screen.getByText(/ver mi donación/i));
  expect(mockPush).toHaveBeenCalledWith("/donar");
});

test("sin donación activa, la tarjeta invita a donar", async () => {
  await render(<PantallaPanico />);
  await screen.findByText(/activa una donación automática/i);
  await fireEvent.press(screen.getByText(/^donar$/i));
  expect(mockPush).toHaveBeenCalledWith("/donar");
});

test("muestra mi unidad con las etiquetas propias del condominio", async () => {
  mockUseAuth.mockReturnValue({
    membresia: {
      rol: "residente",
      condominio: { id: 1, nombre: "Empart", etiqueta_torre: "Block", etiqueta_unidad: "Departamento", genero_unidad: "m" },
      unidad: { numero: "54", torre_nombre: "9" },
      nombre: "Logan", telefono: "",
    },
  });
  await render(<PantallaPanico />);
  await screen.findByText(/block 9, departamento 54/i);
});

test("sin unidad asignada, muestra el mensaje según el género de la etiqueta", async () => {
  await render(<PantallaPanico />);
  await screen.findByText(/sin departamento asignado/i);
});

test("Invitar vecinos navega a la pantalla de invitar", async () => {
  await render(<PantallaPanico />);
  await fireEvent.press(await screen.findByText(/invitar vecinos/i));
  expect(mockPush).toHaveBeenCalledWith("/invitar");
});

test("Directorio no aparece para un residente", async () => {
  await render(<PantallaPanico />);
  await screen.findByText(/invitar vecinos/i);
  expect(screen.queryByText(/^directorio$/i)).toBeNull();
});

test("con rol delegado, Directorio navega al directorio", async () => {
  mockUseAuth.mockReturnValue({
    membresia: {
      rol: "delegado",
      condominio: { id: 1, nombre: "Empart", etiqueta_torre: "Block", etiqueta_unidad: "Departamento", genero_unidad: "m" },
      unidad: null,
      nombre: "Logan", telefono: "",
    },
  });
  await render(<PantallaPanico />);
  await fireEvent.press(await screen.findByText(/^directorio$/i));
  expect(mockPush).toHaveBeenCalledWith("/directorio");
});

test("muestra las alertas activas y cada una navega a su detalle", async () => {
  jest.spyOn(alertasApi, "listarAlertas").mockResolvedValue([
    { id: 9, tipo_display: "Robo", estado: "activa", estado_display: "Activa" } as any,
  ]);
  await render(<PantallaPanico />);
  await fireEvent.press(await screen.findByText(/robo/i));
  expect(mockPush).toHaveBeenCalledWith("/alertas/9");
});

test("sin alertas activas, muestra 'Sin alertas activas.'", async () => {
  await render(<PantallaPanico />);
  await screen.findByText(/sin alertas activas/i);
});

test("si fallan las tarjetas secundarias (donación/alertas), el botón de pánico sigue funcionando", async () => {
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockRejectedValue(new Error("sin red"));
  jest.spyOn(alertasApi, "listarAlertas").mockRejectedValue(new Error("sin red"));
  const enviarSpy = jest.spyOn(enviarAlertaModulo, "enviarAlerta").mockResolvedValue({ id: 1 } as any);
  await render(<PantallaPanico />);
  jest.useFakeTimers();
  await fireEvent(screen.getByTestId("boton-panico"), "pressIn");
  await act(async () => {
    await jest.advanceTimersByTimeAsync(2000);
  });
  jest.useRealTimers();
  expect(enviarSpy).toHaveBeenCalled();
});
```

- [ ] **Step 3: Correr los tests para confirmar que fallan**

Run: `npm test -- "(vecino)/index.test.tsx"`
Expected: FAIL -- no se encuentran los textos nuevos (la pantalla
todavía no renderiza ninguna tarjeta).

- [ ] **Step 4: Reestructurar `app_movil/src/app/(vecino)/index.tsx`**

Agregar, sin tocar `manejarConfirmar`/`enviandoRef`/el flujo de GPS+envío
existente: `useAuth()` para leer `membresia`; `useRouter()` para
`router.push`; `useState`/`useEffect` para cargar `obtenerMiDonacion()` y
`listarAlertas("activa")` al montar (cada uno con su propio `.catch(() => {})`
-- un fallo en cualquiera de las dos NO debe tocar `error`/bloquear el
botón de pánico, ver Review Focus). Estructura: zona fija arriba sin
scroll (`BotonPanico` + `SelectorTipoAlerta` + `error` + `VentanaCancelar`,
exactamente lo que ya existe hoy, sin tocar su JSX) y, debajo, un
`ScrollView` con, en este orden: tarjeta de donación (resumen + botón
que navega a `/donar`), tarjeta "Mi {etiqueta_unidad en minúscula}"
(mismo armado de texto que `inicio.html`: `{etiqueta_torre} {torre_nombre}, {etiqueta_unidad en minúscula} {numero}`,
o `Sin {etiqueta_unidad en minúscula} asignad{o si genero_unidad === "m", si no a}`
si `unidad` es `null`), botón "Invitar vecinos" que navega a `/invitar`
(+ botón "Directorio" que navega a `/directorio` solo si
`membresia?.rol === "delegado"`, mismo criterio que ya usa
`_layout.tsx`), y tarjeta de alertas activas (cada fila navega a
`/alertas/{id}`, o el texto "Sin alertas activas." si la lista viene
vacía).

- [ ] **Step 5: Correr los tests para confirmar que pasan**

Run: `npm test -- "(vecino)/index.test.tsx"`
Expected: PASS (los 3 ya existentes + los 10 nuevos, 13/13).

- [ ] **Step 6: Correr la suite mobile completa**

Run: `npm test` (dentro de `app_movil/`)
Expected: PASS, sin regresiones.

- [ ] **Step 7: Commit**

```bash
git add app_movil/src/app/"(vecino)"/index.tsx app_movil/src/api/auth.ts app_movil/src/__tests__/app/"(vecino)"/index.test.tsx
git commit -m "feat(mobile): pantalla principal con donación, mi depto, invitar y alertas activas"
```

# Paridad app móvil vs web (números de emergencia, historial de donaciones, cambiar contraseña, eliminar cuenta) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task (decidido con el usuario, mismo método
> que la Tanda 4 de donaciones). Steps use checkbox (`- [ ]`) syntax for
> tracking.

**Goal:** Cerrar los 4 gaps de paridad encontrados entre la web y la app
móvil Mi Barrio+ para el rol residente/delegado: números de emergencia
(lista + proponer), historial de donaciones, cambiar contraseña, y
solicitar eliminación de cuenta.

**Architecture:** Dos `ModelViewSet` nuevos en `alertas/api_views.py`
(reusando el patrón ya establecido por `AlertaViewSet`) para números de
emergencia; el historial de donaciones no toca el backend (ya expuesto);
cambiar contraseña/eliminar cuenta son enlaces `Linking.openURL` hacia la
web existente, sin backend ni pantallas nativas nuevas.

**Tech Stack:** Django 6.1 + DRF (backend), Expo/React Native + Jest/RTL
(mobile), mismos patrones ya usados en el proyecto.

**Spec:** `docs/superpowers/specs/2026-10-25-app-movil-paridad-web-design.md`

## Global Constraints

- TDD obligatorio: cada paso de test se escribe y se corre en rojo antes
  del código que lo hace pasar.
- Suite completa en verde antes de cada commit (backend:
  `./venv/Scripts/python.exe manage.py test`; mobile: `npm test` dentro de
  `app_movil/`).
- Cualquier ViewSet nuevo de la API mezcla `CondominioQuerysetMixin` y
  nunca confía en un `condominio`/`autor` que mande el cliente sin
  resolverlo server-side.
- Si un ViewSet sobreescribe `get_permissions()`, comparar contra
  `self.action`, nunca contra `self.request.method` (bug ya conocido en
  este proyecto).
- Sin paginación nueva (D-07 del diseño previo de la API): los endpoints
  nuevos de este plan devuelven listas planas, igual que
  `GET /api/v1/alertas/`.
- Mobile: `jest.restoreAllMocks()` no limpia el historial de llamadas de
  mocks pre-armados por `jest-expo` (ej. `AppState.addEventListener`) --
  agregar `jest.clearAllMocks()` en `afterEach` solo si el test nuevo usa
  uno de esos mocks pre-armados.

## Review Focus

- Proponer un número sin `categoria`/`nombre`/`telefono` debe rechazarse
  (igual que `PropuestaNumeroEmergenciaForm` en la web) -- cubierto en
  Task 2.
- Un usuario autenticado sin `Membresia` propia que intente
  `POST /api/v1/propuestas-numero-emergencia/` debe recibir un 403 claro,
  no un 500 -- cubierto en Task 2.
- La pantalla de donaciones con `pagos: []` (nunca donó) no debe mostrar
  una lista vacía confusa ni romperse -- cubierto en Task 5.
- Un teléfono con espacios (ej. "600 600 5000") no debe pasarse tal cual a
  `Linking.openURL("tel:...")` -- cubierto en Task 4.
- Un residente de un condominio no debe ver ni poder proponer números de
  emergencia de otro condominio -- cubierto en Tasks 1 y 2.

---

### Task 1: Backend -- listar números de emergencia (API)

**Files:**
- Modify: `alertas/serializers.py` (agregar `NumeroEmergenciaSerializer`)
- Modify: `alertas/api_views.py` (agregar `NumeroEmergenciaViewSet`)
- Modify: `alertas/api_urls.py` (registrar la ruta nueva)
- Test: `alertas/tests.py` (agregar `NumeroEmergenciaViewSetTests`)

**Interfaces:**
- Consumes: `condominio_de_la_api` y `CondominioQuerysetMixin`
  (`core/permissions.py`, ya existen), `NUMEROS_NACIONALES`/`NumeroEmergencia`
  (`alertas/models.py`, ya existen).
- Produces: `GET /api/v1/numeros-emergencia/` (nombre de ruta
  `numero-emergencia-list`) -- lista plana de objetos
  `{id, categoria, categoria_display, nombre, telefono, es_nacional}`.

- [ ] **Step 1: Escribir el test que falla**

```python
class NumeroEmergenciaViewSetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test API Numeros", plan="premium")
        cls.otro_condominio = Condominio.objects.create(nombre="Test API Numeros B", plan="premium")

    def setUp(self):
        self.residente = crear_membresia(self.condominio, "residente", username="api_num_residente")

    def test_precarga_los_nacionales_y_los_devuelve(self):
        from .models import NUMEROS_NACIONALES
        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("numero-emergencia-list"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), len(NUMEROS_NACIONALES))
        nombres = {n["nombre"] for n in r.json()}
        self.assertIn("Bomberos", nombres)

    def test_marca_es_nacional(self):
        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("numero-emergencia-list"))
        bomberos = next(n for n in r.json() if n["nombre"] == "Bomberos")
        self.assertTrue(bomberos["es_nacional"])

    def test_incluye_categoria_display(self):
        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("numero-emergencia-list"))
        bomberos = next(n for n in r.json() if n["nombre"] == "Bomberos")
        self.assertEqual(bomberos["categoria_display"], "Bomberos")

    def test_no_ve_numeros_de_otro_condominio(self):
        from .models import NumeroEmergencia
        NumeroEmergencia.objects.create(condominio=self.otro_condominio, categoria="otro", nombre="Conserjería B", telefono="999")
        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("numero-emergencia-list"))
        nombres = {n["nombre"] for n in r.json()}
        self.assertNotIn("Conserjería B", nombres)

    def test_sin_condominio_activo_devuelve_403(self):
        devquad = crear_devquad("api_num_devquad_sin_condominio")
        self.client.force_login(devquad)
        r = self.client.get(reverse("numero-emergencia-list"))
        self.assertEqual(r.status_code, 403)
```

- [ ] **Step 2: Correr el test para confirmar que falla**

Run: `./venv/Scripts/python.exe manage.py test alertas.tests.NumeroEmergenciaViewSetTests -v 2`
Expected: FAIL -- `NoReverseMatch` (`numero-emergencia-list` no existe todavía).

- [ ] **Step 3: Implementar `NumeroEmergenciaSerializer` en `alertas/serializers.py`**

`ModelSerializer` sobre `NumeroEmergencia`. Campos:
`["id", "categoria", "categoria_display", "nombre", "telefono", "es_nacional"]`,
todos de solo lectura (`read_only_fields` = los mismos, es un serializer de
lectura). `categoria_display = serializers.CharField(source="get_categoria_display", read_only=True)`
(mismo patrón que `AlertaSerializer.tipo_display`). `es_nacional` ya es una
`@property` del modelo -- DRF la serializa sola al estar en `fields`.

- [ ] **Step 4: Implementar `NumeroEmergenciaViewSet` en `alertas/api_views.py`**

```python
class NumeroEmergenciaViewSet(CondominioQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = NumeroEmergencia.objects.all()
    serializer_class = NumeroEmergenciaSerializer
    permission_classes = [IsAuthenticated, TieneCondominioActivo]
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        condominio = condominio_de_la_api(self.request)
        if condominio is not None:
            for categoria, nombre, telefono in NUMEROS_NACIONALES:
                NumeroEmergencia.objects.get_or_create(
                    condominio=condominio, nombre=nombre, defaults={"categoria": categoria, "telefono": telefono},
                )
        return super().get_queryset()
```

(Mismo bloque de sincronización que `NumeroEmergenciaListView.get_queryset`
en `alertas/views.py` -- `super().get_queryset()` aplica el filtro de
`CondominioQuerysetMixin` después de sincronizar.) Importar
`NUMEROS_NACIONALES`, `NumeroEmergencia` desde `.models`;
`condominio_de_la_api`, `CondominioQuerysetMixin`, `TieneCondominioActivo`
desde `core.permissions` (agregarlos al import ya existente en el archivo).

- [ ] **Step 5: Registrar la ruta en `alertas/api_urls.py`**

```python
router.register("numeros-emergencia", NumeroEmergenciaViewSet, basename="numero-emergencia")
```

- [ ] **Step 6: Correr el test para confirmar que pasa**

Run: `./venv/Scripts/python.exe manage.py test alertas.tests.NumeroEmergenciaViewSetTests -v 2`
Expected: PASS (5/5).

- [ ] **Step 7: Correr la suite completa**

Run: `./venv/Scripts/python.exe manage.py test`
Expected: PASS, sin regresiones.

- [ ] **Step 8: Commit**

```bash
git add alertas/serializers.py alertas/api_views.py alertas/api_urls.py alertas/tests.py
git commit -m "feat(api): exponer listado de números de emergencia para la app móvil"
```

---

### Task 2: Backend -- proponer y listar mis propuestas (API)

**Files:**
- Modify: `alertas/serializers.py` (agregar `PropuestaNumeroEmergenciaSerializer`)
- Modify: `alertas/api_views.py` (agregar `PropuestaNumeroEmergenciaViewSet`)
- Modify: `alertas/api_urls.py` (registrar la ruta nueva)
- Test: `alertas/tests.py` (agregar `PropuestaNumeroEmergenciaViewSetTests`)

**Interfaces:**
- Consumes: `PropuestaNumeroEmergencia` (`alertas/models.py`, ya existe,
  `estado` default `"pendiente"`).
- Produces: `GET/POST /api/v1/propuestas-numero-emergencia/` (nombre de
  ruta `propuesta-numero-emergencia-list`) -- `GET` devuelve solo las
  propuestas de quien pregunta (`autor=membresia`), objetos
  `{id, categoria, categoria_display, nombre, telefono, nota, estado, estado_display, fecha_creacion}`;
  `POST` acepta `{categoria, nombre, telefono, nota}` (`nota` opcional) y
  crea una propuesta en estado `"pendiente"`.

- [ ] **Step 1: Escribir el test que falla**

```python
class PropuestaNumeroEmergenciaViewSetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test API Propuestas", plan="premium")

    def setUp(self):
        self.residente = crear_membresia(self.condominio, "residente", username="api_prop_residente")
        self.otro_residente = crear_membresia(self.condominio, "residente", username="api_prop_otro_residente")

    def test_cualquier_rol_puede_proponer(self):
        from .models import PropuestaNumeroEmergencia
        self.client.force_login(self.residente.user)
        r = self.client.post(
            reverse("propuesta-numero-emergencia-list"),
            {"categoria": "electricidad", "nombre": "CGE", "telefono": "800 800 767", "nota": "De mi boleta"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201)
        propuesta = PropuestaNumeroEmergencia.objects.get(condominio=self.condominio)
        self.assertEqual(propuesta.autor, self.residente)
        self.assertEqual(propuesta.estado, "pendiente")

    def test_requiere_categoria(self):
        self.client.force_login(self.residente.user)
        r = self.client.post(
            reverse("propuesta-numero-emergencia-list"),
            {"nombre": "CGE", "telefono": "800 800 767"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("categoria", r.json())

    def test_devquad_sin_membresia_no_puede_proponer(self):
        devquad = crear_devquad("api_prop_devquad")
        self.client.force_login(devquad)
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))
        r = self.client.post(
            reverse("propuesta-numero-emergencia-list"),
            {"categoria": "otro", "nombre": "X", "telefono": "123"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 403)

    def test_solo_ve_sus_propias_propuestas(self):
        from .models import PropuestaNumeroEmergencia
        PropuestaNumeroEmergencia.objects.create(
            condominio=self.condominio, autor=self.otro_residente, categoria="otro", nombre="De otro vecino", telefono="111",
        )
        self.client.force_login(self.residente.user)
        r = self.client.get(reverse("propuesta-numero-emergencia-list"))
        self.assertEqual(r.json(), [])
```

- [ ] **Step 2: Correr el test para confirmar que falla**

Run: `./venv/Scripts/python.exe manage.py test alertas.tests.PropuestaNumeroEmergenciaViewSetTests -v 2`
Expected: FAIL -- `NoReverseMatch`.

- [ ] **Step 3: Implementar `PropuestaNumeroEmergenciaSerializer` en `alertas/serializers.py`**

`ModelSerializer` sobre `PropuestaNumeroEmergencia`. Campos:
`["id", "categoria", "categoria_display", "nombre", "telefono", "nota", "estado", "estado_display", "fecha_creacion"]`.
`categoria_display`/`estado_display` vía `source="get_..._display"` (mismo
patrón de Task 1/`AlertaSerializer`). `read_only_fields = ["estado"]`
(el cliente nunca manda `estado`, el modelo ya lo pone en `"pendiente"`).
**Declarar `categoria` explícito como requerido**
(`categoria = serializers.ChoiceField(choices=CATEGORIA_NUMERO_CHOICES, required=True)`
o equivalente) -- el modelo tiene `default="otro"`, que por sí solo haría
que `ModelSerializer` la marque como no requerida, a diferencia de
`PropuestaNumeroEmergenciaForm` en la web, que sí la exige.

- [ ] **Step 4: Implementar `PropuestaNumeroEmergenciaViewSet` en `alertas/api_views.py`**

```python
class PropuestaNumeroEmergenciaViewSet(CondominioQuerysetMixin, viewsets.ModelViewSet):
    queryset = PropuestaNumeroEmergencia.objects.all()
    serializer_class = PropuestaNumeroEmergenciaSerializer
    permission_classes = [IsAuthenticated, TieneCondominioActivo]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        membresia = getattr(self.request.user, "membresia", None)
        return super().get_queryset().filter(autor=membresia)

    def perform_create(self, serializer):
        membresia = getattr(self.request.user, "membresia", None)
        if membresia is None:
            raise PermissionDenied("Proponer un número requiere ser residente/delegado de un condominio.")
        serializer.save(condominio=membresia.condominio, autor=membresia)
```

(Mismo patrón que `AlertaViewSet.perform_create` para el 403 sin
Membresia.) Importar `PropuestaNumeroEmergencia` desde `.models`.

- [ ] **Step 5: Registrar la ruta en `alertas/api_urls.py`**

```python
router.register("propuestas-numero-emergencia", PropuestaNumeroEmergenciaViewSet, basename="propuesta-numero-emergencia")
```

- [ ] **Step 6: Correr el test para confirmar que pasa**

Run: `./venv/Scripts/python.exe manage.py test alertas.tests.PropuestaNumeroEmergenciaViewSetTests -v 2`
Expected: PASS (4/4).

- [ ] **Step 7: Correr la suite completa**

Run: `./venv/Scripts/python.exe manage.py test`
Expected: PASS, sin regresiones.

- [ ] **Step 8: Commit**

```bash
git add alertas/serializers.py alertas/api_views.py alertas/api_urls.py alertas/tests.py
git commit -m "feat(api): permitir proponer y listar propuestas propias de números de emergencia"
```

---

### Task 3: Mobile -- cliente API de números de emergencia

**Files:**
- Create: `app_movil/src/api/numerosEmergencia.ts`
- Test: `app_movil/src/api/numerosEmergencia.test.ts`

**Interfaces:**
- Consumes: `apiFetch` (`app_movil/src/api/client.ts`, ya existe), las
  rutas producidas por Tasks 1 y 2.
- Produces: `NumeroEmergenciaOut`, `PropuestaOut` (tipos),
  `listarNumerosEmergencia(): Promise<NumeroEmergenciaOut[]>`,
  `listarMisPropuestas(): Promise<PropuestaOut[]>`,
  `proponerNumero(payload: {categoria: string; nombre: string; telefono: string; nota?: string}): Promise<PropuestaOut>`.

- [ ] **Step 1: Escribir el test que falla**

```typescript
jest.mock("./client");

import { listarNumerosEmergencia, listarMisPropuestas, proponerNumero } from "./numerosEmergencia";
import { apiFetch } from "./client";

afterEach(() => jest.restoreAllMocks());

test("listarNumerosEmergencia pide GET /api/v1/numeros-emergencia/", async () => {
  (apiFetch as jest.Mock).mockResolvedValue([]);
  await listarNumerosEmergencia();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/numeros-emergencia/");
});

test("listarMisPropuestas pide GET /api/v1/propuestas-numero-emergencia/", async () => {
  (apiFetch as jest.Mock).mockResolvedValue([]);
  await listarMisPropuestas();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/propuestas-numero-emergencia/");
});

test("proponerNumero pide POST /api/v1/propuestas-numero-emergencia/ con el payload", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ id: 1 });
  await proponerNumero({ categoria: "electricidad", nombre: "CGE", telefono: "800 800 767" });
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/propuestas-numero-emergencia/", {
    method: "POST",
    body: JSON.stringify({ categoria: "electricidad", nombre: "CGE", telefono: "800 800 767" }),
  });
});
```

- [ ] **Step 2: Correr el test para confirmar que falla**

Run: `npm test -- numerosEmergencia.test.ts` (dentro de `app_movil/`)
Expected: FAIL -- no se puede resolver el módulo `./numerosEmergencia`.

- [ ] **Step 3: Implementar `app_movil/src/api/numerosEmergencia.ts`**

Mismo estilo que `app_movil/src/api/alertas.ts`. Tipos:

```typescript
export type NumeroEmergenciaOut = {
  id: number;
  categoria: string;
  categoria_display: string;
  nombre: string;
  telefono: string;
  es_nacional: boolean;
};

export type PropuestaOut = {
  id: number;
  categoria: string;
  categoria_display: string;
  nombre: string;
  telefono: string;
  nota: string;
  estado: "pendiente" | "aprobada" | "rechazada";
  estado_display: string;
  fecha_creacion: string;
};
```

`proponerNumero` manda `JSON.stringify(payload)` igual que `crearAlerta`
en `alertas.ts` (sin agregar campos que el payload no traiga -- `nota` es
opcional, se manda solo si vino).

- [ ] **Step 4: Correr el test para confirmar que pasa**

Run: `npm test -- numerosEmergencia.test.ts`
Expected: PASS (3/3).

- [ ] **Step 5: Commit**

```bash
git add app_movil/src/api/numerosEmergencia.ts app_movil/src/api/numerosEmergencia.test.ts
git commit -m "feat(mobile): cliente API de números de emergencia"
```

---

### Task 4: Mobile -- pantalla "Números de emergencia"

**Files:**
- Create: `app_movil/src/app/(vecino)/numeros-emergencia/index.tsx`
- Modify: `app_movil/src/app/(vecino)/_layout.tsx`
- Test: `app_movil/src/__tests__/app/(vecino)/numeros-emergencia/index.test.tsx`

**Interfaces:**
- Consumes: `listarNumerosEmergencia`, `listarMisPropuestas`,
  `proponerNumero` (Task 3).
- Produces: pantalla registrada en el Drawer como "Números de emergencia".

- [ ] **Step 1: Escribir los tests que fallan**

```typescript
import { render, fireEvent, screen } from "@testing-library/react-native";
import * as Linking from "expo-linking";
import NumerosEmergenciaScreen from "@/app/(vecino)/numeros-emergencia/index";
import * as numerosApi from "@/api/numerosEmergencia";

afterEach(() => jest.restoreAllMocks());

test("muestra la lista de números con su categoría", async () => {
  jest.spyOn(numerosApi, "listarNumerosEmergencia").mockResolvedValue([
    { id: 1, categoria: "bomberos", categoria_display: "Bomberos", nombre: "Bomberos", telefono: "132", es_nacional: true },
  ]);
  jest.spyOn(numerosApi, "listarMisPropuestas").mockResolvedValue([]);
  await render(<NumerosEmergenciaScreen />);
  await screen.findByText(/bomberos/i);
  expect(screen.getByText(/132/)).toBeTruthy();
});

test("al tocar un número, llama con tel: limpiando los espacios del teléfono", async () => {
  jest.spyOn(numerosApi, "listarNumerosEmergencia").mockResolvedValue([
    { id: 2, categoria: "salud", categoria_display: "Salud/Ambulancia", nombre: "Salud Responde", telefono: "600 360 7777", es_nacional: true },
  ]);
  jest.spyOn(numerosApi, "listarMisPropuestas").mockResolvedValue([]);
  const abrirSpy = jest.spyOn(Linking, "openURL").mockResolvedValue(true);
  await render(<NumerosEmergenciaScreen />);
  await fireEvent.press(await screen.findByText(/salud responde/i));
  expect(abrirSpy).toHaveBeenCalledWith("tel:6003607777");
});

test("muestra las propuestas propias con su estado", async () => {
  jest.spyOn(numerosApi, "listarNumerosEmergencia").mockResolvedValue([]);
  jest.spyOn(numerosApi, "listarMisPropuestas").mockResolvedValue([
    { id: 5, categoria: "electricidad", categoria_display: "Electricidad", nombre: "CGE", telefono: "800 800 767", nota: "", estado: "pendiente", estado_display: "Pendiente", fecha_creacion: "2026-10-01T00:00:00Z" },
  ]);
  await render(<NumerosEmergenciaScreen />);
  await screen.findByText(/cge/i);
  expect(screen.getByText(/pendiente/i)).toBeTruthy();
});

test("al enviar el formulario de proponer, llama a proponerNumero y confirma", async () => {
  jest.spyOn(numerosApi, "listarNumerosEmergencia").mockResolvedValue([]);
  jest.spyOn(numerosApi, "listarMisPropuestas").mockResolvedValue([]);
  const proponerSpy = jest.spyOn(numerosApi, "proponerNumero").mockResolvedValue({
    id: 9, categoria: "otro", categoria_display: "Otro", nombre: "Conserjería", telefono: "123", nota: "", estado: "pendiente", estado_display: "Pendiente", fecha_creacion: "2026-10-01T00:00:00Z",
  });
  await render(<NumerosEmergenciaScreen />);
  await fireEvent.press(await screen.findByText(/proponer un número/i));
  fireEvent.changeText(screen.getByPlaceholderText(/nombre/i), "Conserjería");
  fireEvent.changeText(screen.getByPlaceholderText(/teléfono/i), "123");
  await fireEvent.press(screen.getByText(/^enviar$/i));
  expect(proponerSpy).toHaveBeenCalled();
  await screen.findByText(/gracias.*pendiente de revisión/i);
});

test("si falla la carga, muestra error y 'Reintentar'", async () => {
  jest.spyOn(numerosApi, "listarNumerosEmergencia").mockRejectedValueOnce(new Error("sin red")).mockResolvedValueOnce([]);
  jest.spyOn(numerosApi, "listarMisPropuestas").mockResolvedValue([]);
  await render(<NumerosEmergenciaScreen />);
  await screen.findByText(/no se pudo cargar/i);
  await fireEvent.press(screen.getByText(/reintentar/i));
});
```

- [ ] **Step 2: Correr los tests para confirmar que fallan**

Run: `npm test -- "numeros-emergencia/index.test.tsx"`
Expected: FAIL -- no se puede resolver `@/app/(vecino)/numeros-emergencia/index`.

- [ ] **Step 3: Implementar `app_movil/src/app/(vecino)/numeros-emergencia/index.tsx`**

Mismo estilo que `donar/index.tsx`/`perfil/index.tsx` (carga con
`useEffect`, estado de error + "Reintentar", `StyleSheet.create` con
`colores` del theme). Estructura: lista de números (cada fila tocable,
`Linking.openURL(`tel:${telefono.replace(/\s+/g, "")}`)`), debajo sección
"Mis propuestas" (si hay alguna), debajo un botón "Proponer un número" que
revela un formulario inline (categoría -- puede ser un `TextInput` simple
o un selector, a criterio de quien construya; nombre; teléfono; nota
opcional) con botón "Enviar" que llama `proponerNumero` y, al terminar,
muestra "Gracias, tu propuesta quedó pendiente de revisión." (mismo texto
que `ProponerNumeroEmergenciaView.form_valid` en la web) y refresca
`listarMisPropuestas`.

- [ ] **Step 4: Registrar la pantalla en el Drawer**

En `app_movil/src/app/(vecino)/_layout.tsx`, agregar
`<Drawer.Screen name="numeros-emergencia/index" options={{ title: "Números de emergencia" }} />`
junto a `alertas/index`.

- [ ] **Step 5: Correr los tests para confirmar que pasan**

Run: `npm test -- "numeros-emergencia/index.test.tsx"`
Expected: PASS (5/5).

- [ ] **Step 6: Correr la suite mobile completa**

Run: `npm test` (dentro de `app_movil/`)
Expected: PASS, sin regresiones.

- [ ] **Step 7: Commit**

```bash
git add app_movil/src/app/"(vecino)"/numeros-emergencia/index.tsx app_movil/src/app/"(vecino)"/_layout.tsx app_movil/src/__tests__/app/"(vecino)"/numeros-emergencia/index.test.tsx
git commit -m "feat(mobile): pantalla de números de emergencia (listar, llamar, proponer)"
```

---

### Task 5: Mobile -- historial de donaciones en la pantalla "Donar"

**Files:**
- Modify: `app_movil/src/app/(vecino)/donar/index.tsx`
- Modify: `app_movil/src/__tests__/app/(vecino)/donar/index.test.tsx`

**Interfaces:**
- Consumes: `datos.pagos`, `datos.total_donado`, `datos.cantidad_aportes`
  (ya devueltos por `obtenerMiDonacion()`, `app_movil/src/api/donaciones.ts`
  -- sin cambios en ese archivo).

- [ ] **Step 1: Escribir los tests que fallan**

```typescript
test("muestra el total donado y la cantidad de aportes cuando hay historial", async () => {
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({
    donacion_actual: null,
    pagos: [{ estado: "aprobado", monto: "2000.00", fecha_creacion: "2026-09-01T00:00:00Z" }],
    total_donado: "2000.00",
    cantidad_aportes: 1,
  });
  await render(<DonarScreen />);
  await screen.findByText(/2\.000/);
  expect(screen.getByText(/1 aporte/i)).toBeTruthy();
});

test("sin historial, muestra un mensaje en vez de una lista vacía", async () => {
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({
    donacion_actual: null, pagos: [], total_donado: "0.00", cantidad_aportes: 0,
  });
  await render(<DonarScreen />);
  await screen.findByText(/todavía no tienes donaciones/i);
});
```

(Agregar estos dos tests al archivo existente, sin tocar los que ya hay --
siguen pasando porque ninguno asume que el historial NO se muestra.)

- [ ] **Step 2: Correr los tests para confirmar que fallan**

Run: `npm test -- "donar/index.test.tsx"`
Expected: FAIL -- no se encuentra el texto del total/mensaje (la pantalla
todavía no los renderiza).

- [ ] **Step 3: Implementar la sección de historial en `donar/index.tsx`**

Debajo del bloque de estado/botón que ya existe, agregar una sección fija
(se muestra siempre, tenga o no donación activa) que renderiza
`datos.total_donado`/`datos.cantidad_aportes` (texto tipo
"Has aportado $2.000 en 1 aporte") y la lista de `datos.pagos`
(fecha + monto + estado, uno por fila). Si `datos.pagos.length === 0`,
mostrar "Todavía no tienes donaciones registradas." en vez de la lista y
los totales.

- [ ] **Step 4: Correr los tests para confirmar que pasan**

Run: `npm test -- "donar/index.test.tsx"`
Expected: PASS (todos, los viejos y los 2 nuevos).

- [ ] **Step 5: Correr la suite mobile completa**

Run: `npm test` (dentro de `app_movil/`)
Expected: PASS, sin regresiones.

- [ ] **Step 6: Commit**

```bash
git add app_movil/src/app/"(vecino)"/donar/index.tsx app_movil/src/__tests__/app/"(vecino)"/donar/index.test.tsx
git commit -m "feat(mobile): mostrar historial de donaciones en la pantalla Donar"
```

---

### Task 6: Mobile -- cambiar contraseña y eliminar cuenta desde "Mi perfil"

**Files:**
- Modify: `app_movil/src/app/(vecino)/perfil/index.tsx`
- Modify: `app_movil/src/__tests__/app/(vecino)/perfil/index.test.tsx`

**Interfaces:**
- Consumes: `API_BASE_URL` (`app_movil/src/api/client.ts`, ya exportado),
  `Linking.openURL` (`expo-linking`, ya usado en `donar/index.tsx`).

- [ ] **Step 1: Escribir los tests que fallan**

```typescript
import * as Linking from "expo-linking";
import { API_BASE_URL } from "@/api/client";

test("el botón Cambiar contraseña abre la página web en el navegador externo", async () => {
  jest.spyOn(authApi, "obtenerMiPerfil").mockResolvedValue({
    rol: "residente", condominio: { id: 1, nombre: "X" }, unidad: null,
    nombre: "Ana Pérez", telefono: "", first_name: "Ana", last_name: "Pérez", email: "ana@test.cl",
  });
  const abrirSpy = jest.spyOn(Linking, "openURL").mockResolvedValue(true);
  await render(<PantallaPerfil />);
  await fireEvent.press(await screen.findByText(/cambiar contraseña/i));
  expect(abrirSpy).toHaveBeenCalledWith(`${API_BASE_URL}/mi-perfil/cambiar-contrasena/`);
});

test("el botón Solicitar eliminación de cuenta abre la página web en el navegador externo", async () => {
  jest.spyOn(authApi, "obtenerMiPerfil").mockResolvedValue({
    rol: "residente", condominio: { id: 1, nombre: "X" }, unidad: null,
    nombre: "Ana Pérez", telefono: "", first_name: "Ana", last_name: "Pérez", email: "ana@test.cl",
  });
  const abrirSpy = jest.spyOn(Linking, "openURL").mockResolvedValue(true);
  await render(<PantallaPerfil />);
  await fireEvent.press(await screen.findByText(/solicitar eliminación de cuenta/i));
  expect(abrirSpy).toHaveBeenCalledWith(`${API_BASE_URL}/mi-perfil/eliminar-cuenta/`);
});
```

- [ ] **Step 2: Correr los tests para confirmar que fallan**

Run: `npm test -- "perfil/index.test.tsx"`
Expected: FAIL -- no existen los textos "Cambiar contraseña"/"Solicitar
eliminación de cuenta" en la pantalla todavía.

- [ ] **Step 3: Agregar los dos botones en `perfil/index.tsx`**

Debajo del botón "Guardar" que ya existe, dos `Pressable` que llaman
`Linking.openURL(`${API_BASE_URL}/mi-perfil/cambiar-contrasena/`)` y
`Linking.openURL(`${API_BASE_URL}/mi-perfil/eliminar-cuenta/`)`
respectivamente (importar `* as Linking from "expo-linking"` y
`API_BASE_URL` desde `@/api/client`, mismo patrón que
`donar/index.tsx: manejarDonar`).

- [ ] **Step 4: Correr los tests para confirmar que pasan**

Run: `npm test -- "perfil/index.test.tsx"`
Expected: PASS (todos, los viejos y los 2 nuevos).

- [ ] **Step 5: Correr la suite mobile completa**

Run: `npm test` (dentro de `app_movil/`)
Expected: PASS, sin regresiones.

- [ ] **Step 6: Commit**

```bash
git add app_movil/src/app/"(vecino)"/perfil/index.tsx app_movil/src/__tests__/app/"(vecino)"/perfil/index.test.tsx
git commit -m "feat(mobile): accesos a cambiar contraseña y eliminar cuenta desde Mi perfil"
```

# App móvil Tanda 4 -- Donaciones Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dejar que un residente/delegado active, consulte y cancele una donación mensual automática a DevQuad desde la app móvil, igual que ya puede hacerlo en el panel web.

**Architecture:** El panel web ya tiene el flujo completo (`pagos/views.py`: `DonarView`/`CancelarDonacionRecurrenteView`/`MisDonacionesView`, `pagos/mercadopago_client.py`: `crear_suscripcion_recurrente`/`cancelar_suscripcion_recurrente`) pero son vistas Django de sesión por cookie, no alcanzables por la app (autenticada con JWT). Se agregan 3 endpoints nuevos en `/api/v1/pagos/` que reusan esa misma lógica de negocio, y una pantalla nueva en `app_movil/src/app/(vecino)/donar/`. El pago en sí nunca se construye nativo: la app pide la URL de autorización de Mercado Pago al backend y la abre con `Linking.openURL` (navegador externo) -- decisión explícita para no entrar en el régimen de In-App Purchase de Apple/Google, ya que es una donación voluntaria que no desbloquea nada dentro de la app.

**Tech Stack:** Django REST Framework (serializers nuevos, sin ModelViewSet -- cada endpoint tiene su propia forma de entrada/salida, igual que el resto de `core/api_views.py`), Expo Router + TypeScript + `expo-linking` del lado de la app.

**Spec:** `docs/superpowers/specs/2026-10-19-app-movil-mi-barrio-design.md` (sección "Pendientes" dentro de "Non-goals") -- fuera de alcance de esa fase original, se retoma ahora como Tanda 4, **acotada solo a donaciones** (foto en alertas sigue descartada para v1 por la Ley 21.719 y por velocidad; modo silencioso sigue diferido por necesitar código nativo -- ninguno de los dos entra en este plan).

## Global Constraints

- Monto fijo, nunca lo elige quien dona: `pagos/views.py` `MONTO_DONACION = Decimal("2000")`.
- El pago se abre en navegador externo (`expo-linking`, ya es dependencia del proyecto) -- nunca un checkout nativo dentro de la app.
- Los nuevos endpoints van bajo el prefijo ya existente `/api/v1/` (ver `config/urls.py`, `API_V1_PREFIX`), en un archivo nuevo `pagos/api_urls.py` -- mismo patrón que `alertas.api_urls`/`comunicacion.api_urls`/`notificaciones.api_urls`.
- Autenticación: `IsAuthenticated` (JWT o sesión, igual que el resto de `core/api_views.py` vía `REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']`). No se reusa `EsDevquad`/`TieneCondominioActivo` de `core/permissions.py` -- una donación es personal de un residente/delegado (`SuscripcionRecurrente.membresia`), no del condominio activo de un devquad.
- No se modifica el webhook (`WebhookMercadoPagoView`) ni `sincronizar_estado_suscripcion` -- ya procesan cualquier `SuscripcionRecurrente` sin importar si se creó desde el panel web o desde la app.
- Dinero en las respuestas de la API: `serializers.DecimalField` sin tocar `COERCE_DECIMAL_TO_STRING` (no está en `config/settings.py`, por lo que ya es `True`, el default de DRF) -- `monto`/`total_donado` llegan como string (`"2000.00"`), nunca como float, para evitar errores de redondeo. El tipo TypeScript del lado de la app es `string`.

## Review Focus

- Un devquad (sin Membresía propia) golpea estos endpoints -- tiene que dar 409 ("Esta cuenta no tiene una membresía personal."), nunca un `AttributeError` sobre `None.condominio`. No es alcanzable desde la UI de la app (devquad nunca ve las rutas `(vecino)/`), pero la API tiene que defenderse igual, mismo criterio que `AlertaViewSet.perform_create`.
- Residente sin email configurado en "Mi perfil" intenta donar -- 400 con un mensaje que lo mande ahí, igual que el panel web, no una request rota a Mercado Pago con `payer_email` vacío.
- Ya existe una donación `pendiente` o `autorizada` y la persona intenta activar otra -- 409, nunca una segunda `SuscripcionRecurrente` duplicada para la misma Membresía.
- `MERCADOPAGO_ACCESS_TOKEN` no configurada (ambiente de desarrollo/sandbox sin la llave) -- 400 claro, no un 500 contra la API de Mercado Pago sin credenciales.
- Mercado Pago rechaza la solicitud de autorización (`crear_suscripcion_recurrente` devuelve `None`, ver llamada real a su SDK) -- la `SuscripcionRecurrente` recién creada se borra (rollback), nunca queda un registro huérfano sin `mercadopago_preapproval_id`.

---

### Task 1: API de donaciones (3 endpoints)

**Files:**
- Create: `pagos/api_views.py`
- Create: `pagos/api_urls.py`
- Create: `pagos/serializers.py`
- Modify: `config/urls.py` (agregar `path(API_V1_PREFIX, include('pagos.api_urls'))` junto a los otros 3 `include` de API ya existentes)
- Test: `pagos/tests.py` (agregar una clase nueva al final del archivo)

**Interfaces:**
- Consumes: `pagos.models.SuscripcionRecurrente`/`Pago` (ya existen); `pagos.mercadopago_client.crear_suscripcion_recurrente(suscripcion, email, request) -> str | None` y `cancelar_suscripcion_recurrente(suscripcion) -> bool` (ya existen, mismas firmas que usa `pagos/views.py`); `pagos.views._email_del_pagador(request) -> str` y `pagos.views.MONTO_DONACION` (reusar tal cual, importar desde `pagos.views`).
- Produces (para la Tarea 2):
  - `GET /api/v1/pagos/mi-donacion/` -> 200 `{"donacion_actual": {"estado": str, "monto": str, "fecha_creacion": str} | null, "pagos": [{"monto": str, "estado": str, "fecha_creacion": str}], "total_donado": str, "cantidad_aportes": int}`, o 409 `{"detail": "..."}` si `request.user.membresia` es `None`.
  - `POST /api/v1/pagos/donar/` -> 201 `{"url_autorizacion": str}`, o 400/409/502 `{"detail": "..."}` (ver tabla de errores abajo).
  - `POST /api/v1/pagos/donar/cancelar/` -> 200 `{"detail": "Listo, cancelamos tu donación automática. No se harán más cobros."}`, o 400/404/409 `{"detail": "..."}`.

**Tabla de errores de `POST /api/v1/pagos/donar/`** (mismas condiciones que `DonarView`, códigos elegidos para que la app pueda distinguir el caso sin parsear el texto):

| Condición | Status | `detail` |
|---|---|---|
| `request.user.membresia` es `None` | 409 | "Esta cuenta no tiene una membresía personal." |
| `settings.MERCADOPAGO_ACCESS_TOKEN` vacía | 400 | "El pago en línea todavía no está disponible. Escríbenos para donar." |
| `_email_del_pagador(request)` vacío | 400 | "Agrega tu email en «Mi perfil» antes de activar una donación automática." |
| Ya existe `SuscripcionRecurrente` con `tipo="donacion"`, `estado__in=["pendiente","autorizada"]` para esa Membresía | 409 | "Ya tienes una donación automática activa." |
| `crear_suscripcion_recurrente(...)` devuelve `None` | 502 | "No pudimos iniciar la donación automática. Intenta de nuevo en un momento." |

- [ ] **Step 1: Escribir los tests que fallan, para los 3 endpoints**

En `pagos/tests.py`, clase nueva `ApiDonacionesTests(TestCase)`. Seguir el estilo ya usado en `WebhookFirmaTests`/`WebhookMercadoPagoTests` de ese mismo archivo (setUp con `Condominio.objects.create(...)`, `crear_membresia`-equivalente -- revisar cómo lo hace `core/tests.py` si no existe ya un helper en `pagos/tests.py`, y `patch("pagos.api_views.crear_suscripcion_recurrente", ...)` para no llamar a Mercado Pago de verdad). Casos mínimos (uno por fila de la tabla de arriba, más):

```python
def test_mi_donacion_sin_donacion_activa_devuelve_null(self):
    ...
    r = self.client.get(reverse("api-mi-donacion"))
    self.assertEqual(r.status_code, 200)
    self.assertIsNone(r.json()["donacion_actual"])

def test_donar_crea_la_suscripcion_y_devuelve_la_url(self):
    with patch("pagos.api_views.crear_suscripcion_recurrente", return_value="https://mercadopago.cl/autorizar/123"):
        r = self.client.post(reverse("api-donar"))
    self.assertEqual(r.status_code, 201)
    self.assertEqual(r.json()["url_autorizacion"], "https://mercadopago.cl/autorizar/123")
    self.assertTrue(SuscripcionRecurrente.objects.filter(membresia=self.membresia, tipo="donacion").exists())

def test_donar_sin_email_devuelve_400(self):
    # Membresía/usuario con email="" -- confirmar el mensaje exacto de la tabla.
    ...

@override_settings(MERCADOPAGO_ACCESS_TOKEN="")
def test_donar_sin_access_token_configurada_devuelve_400(self):
    r = self.client.post(reverse("api-donar"))
    self.assertEqual(r.status_code, 400)
    self.assertIn("todavía no está disponible", r.json()["detail"])

def test_donar_con_donacion_activa_devuelve_409(self):
    # Crear una SuscripcionRecurrente(tipo="donacion", estado="autorizada") antes.
    ...

def test_donar_si_mercadopago_rechaza_no_deja_registro_huerfano(self):
    with patch("pagos.api_views.crear_suscripcion_recurrente", return_value=None):
        r = self.client.post(reverse("api-donar"))
    self.assertEqual(r.status_code, 502)
    self.assertFalse(SuscripcionRecurrente.objects.filter(membresia=self.membresia).exists())

def test_devquad_sin_membresia_recibe_409_en_los_3_endpoints(self):
    # force_login con un User is_staff=True sin Membresia -- los 3 endpoints.
    ...

def test_cancelar_sin_donacion_activa_devuelve_404(self):
    ...

def test_cancelar_una_donacion_activa_la_marca_cancelada(self):
    with patch("pagos.api_views.cancelar_suscripcion_recurrente", return_value=True):
        r = self.client.post(reverse("api-donar-cancelar"))
    self.assertEqual(r.status_code, 200)
```

- [ ] **Step 2: Correr los tests, confirmar que fallan por `NoReverseMatch`/`ImportError`**

Run: `./venv/Scripts/python.exe manage.py test pagos.tests.ApiDonacionesTests -v 2`
Expected: FAIL -- `NoReverseMatch: Reverse for 'api-mi-donacion' not found` (todavía no existen las urls/vistas).

- [ ] **Step 3: Implementar los serializers en `pagos/serializers.py`**

```python
class PagoResumenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pago
        fields = ["monto", "estado", "fecha_creacion"]

class DonacionActualSerializer(serializers.ModelSerializer):
    class Meta:
        model = SuscripcionRecurrente
        fields = ["estado", "monto", "fecha_creacion"]
```

- [ ] **Step 4: Implementar las 3 vistas en `pagos/api_views.py`**

```python
class MiDonacionApiView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request): ...

class DonarApiView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request): ...

class CancelarDonacionApiView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request): ...
```

Cada una resuelve `membresia = getattr(request.user, "membresia", None)` y devuelve 409 si es `None`, antes de cualquier otra cosa -- igual que las condiciones de `DonarView`/`CancelarDonacionRecurrenteView`, en el mismo orden que la tabla de errores. `MiDonacionApiView.get` construye la respuesta con `DonacionActualSerializer`/`PagoResumenSerializer` y calcula `total_donado`/`cantidad_aportes` igual que `MisDonacionesView.get_context_data` (reusar esa misma lógica, no reinventarla). Anotar cada vista con `@extend_schema` (ver cualquier vista de `core/api_views.py` como ejemplo), consistente con el resto del proyecto.

- [ ] **Step 5: Crear `pagos/api_urls.py` y registrarlo en `config/urls.py`**

```python
# pagos/api_urls.py
urlpatterns = [
    path("pagos/mi-donacion/", api_views.MiDonacionApiView.as_view(), name="api-mi-donacion"),
    path("pagos/donar/", api_views.DonarApiView.as_view(), name="api-donar"),
    path("pagos/donar/cancelar/", api_views.CancelarDonacionApiView.as_view(), name="api-donar-cancelar"),
]
```

Agregar `path(API_V1_PREFIX, include('pagos.api_urls')),` en `config/urls.py` junto a los otros 3 `include` de API.

- [ ] **Step 6: Correr los tests, confirmar que pasan**

Run: `./venv/Scripts/python.exe manage.py test pagos.tests.ApiDonacionesTests -v 2`
Expected: PASS, todos los casos del Step 1.

- [ ] **Step 7: Correr el suite completo de Django**

Run: `./venv/Scripts/python.exe manage.py test`
Expected: PASS -- mismo número de tests que antes + los nuevos, sin ningún FAIL.

- [ ] **Step 8: Commit**

```bash
git add pagos/api_views.py pagos/api_urls.py pagos/serializers.py pagos/tests.py config/urls.py
git commit -m "feat: API de donaciones para la app móvil (Tanda 4)"
```

---

### Task 2: Pantalla "Donar" en la app móvil

**Files:**
- Create: `app_movil/src/api/donaciones.ts`
- Create: `app_movil/src/app/(vecino)/donar/index.tsx`
- Modify: `app_movil/src/app/(vecino)/_layout.tsx` (agregar `<Drawer.Screen name="donar/index" options={{ title: "Donar" }} />`)
- Test: `app_movil/src/api/donaciones.test.ts`
- Test: `app_movil/src/__tests__/app/(vecino)/donar/index.test.tsx`

**Interfaces:**
- Consumes: `apiFetch`/`ErrorDeServidor` de `@/api/client` (ver Tarea 1 para las formas exactas de request/response de los 3 endpoints); `expo-linking` (ya es dependencia del proyecto, ver `app_movil/package.json`).
- Produces: nada que otra tarea consuma (es la última de este plan).

```typescript
// app_movil/src/api/donaciones.ts
export type Donacion = { estado: string; monto: string; fecha_creacion: string };
export type MiDonacion = {
  donacion_actual: Donacion | null;
  pagos: Donacion[];
  total_donado: string;
  cantidad_aportes: number;
};

export function obtenerMiDonacion(): Promise<MiDonacion>;
export function crearDonacion(): Promise<{ url_autorizacion: string }>;
export function cancelarDonacion(): Promise<void>;
```

- [ ] **Step 1: Escribir el test de `donaciones.ts` que falla**

En `app_movil/src/api/donaciones.test.ts`, mismo estilo que `app_movil/src/api/directorio.test.ts` (mock de `apiFetch` vía `jest.mock("./client")`, un test por función: `obtenerMiDonacion` pide `GET /api/v1/pagos/mi-donacion/`, `crearDonacion` pide `POST /api/v1/pagos/donar/` sin body, `cancelarDonacion` pide `POST /api/v1/pagos/donar/cancelar/` sin body).

- [ ] **Step 2: Correr el test, confirmar que falla**

Run: `cd app_movil && npx jest src/api/donaciones.test.ts --watchAll=false`
Expected: FAIL -- `Cannot find module './donaciones'`.

- [ ] **Step 3: Implementar `app_movil/src/api/donaciones.ts`**

Tres funciones finitas, sin lógica -- ver las firmas exactas arriba y las rutas de la Tarea 1 (`/api/v1/pagos/mi-donacion/`, `/api/v1/pagos/donar/`, `/api/v1/pagos/donar/cancelar/`).

- [ ] **Step 4: Correr el test, confirmar que pasa**

Run: `cd app_movil && npx jest src/api/donaciones.test.ts --watchAll=false`
Expected: PASS, 3/3.

- [ ] **Step 5: Escribir los tests de la pantalla que fallan**

En `app_movil/src/__tests__/app/(vecino)/donar/index.test.tsx`, mismo estilo que `app_movil/src/__tests__/app/(vecino)/perfil/index.test.tsx` (mock de `expo-notifications` al inicio del archivo si el runner lo exige, `jest.spyOn` sobre el módulo `@/api/donaciones`, `@testing-library/react-native`). Casos:

```tsx
test("sin donación activa, muestra el monto fijo y un botón Donar", async () => {
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({
    donacion_actual: null, pagos: [], total_donado: "0.00", cantidad_aportes: 0,
  });
  await render(<DonarScreen />);
  await screen.findByText(/\$2[.,]?000/); // el monto fijo, MONTO_DONACION
  expect(screen.getByText(/donar/i)).toBeTruthy();
});

test("al tocar Donar, abre la URL de autorización en el navegador", async () => {
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({ donacion_actual: null, pagos: [], total_donado: "0.00", cantidad_aportes: 0 });
  jest.spyOn(donacionesApi, "crearDonacion").mockResolvedValue({ url_autorizacion: "https://mercadopago.cl/autorizar/123" });
  const abrirSpy = jest.spyOn(Linking, "openURL").mockResolvedValue(true);
  await render(<DonarScreen />);
  await fireEvent.press(await screen.findByText(/donar/i));
  await waitFor(() => expect(abrirSpy).toHaveBeenCalledWith("https://mercadopago.cl/autorizar/123"));
});

test("con una donación activa, muestra el estado y un botón Cancelar en vez de Donar", async () => {
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({
    donacion_actual: { estado: "autorizada", monto: "2000.00", fecha_creacion: "2026-10-01T00:00:00Z" },
    pagos: [], total_donado: "6000.00", cantidad_aportes: 3,
  });
  await render(<DonarScreen />);
  await screen.findByText(/cancelar/i);
});

test("si falla crear la donación, muestra un error en vez de romper", async () => {
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({ donacion_actual: null, pagos: [], total_donado: "0.00", cantidad_aportes: 0 });
  jest.spyOn(donacionesApi, "crearDonacion").mockRejectedValue(new ErrorDeServidor(400, { detail: "Agrega tu email en «Mi perfil» antes de activar una donación automática." }));
  await render(<DonarScreen />);
  await fireEvent.press(await screen.findByText(/donar/i));
  await screen.findByText(/agrega tu email/i);
});
```

- [ ] **Step 6: Correr los tests, confirmar que fallan**

Run: `cd app_movil && npx jest "src/__tests__/app/(vecino)/donar" --watchAll=false`
Expected: FAIL -- el módulo/componente todavía no existe.

- [ ] **Step 7: Implementar `app_movil/src/app/(vecino)/donar/index.tsx`**

Patrón ya usado en `app_movil/src/app/(vecino)/directorio/index.tsx`/`perfil/index.tsx`: `useEffect` llama a `obtenerMiDonacion()` al montar; si `donacion_actual` es `null`, muestra el monto fijo (hardcodeado como texto -- `$2.000`, igual que el backend, no hace falta traerlo de la API) y un botón "Donar" que llama a `crearDonacion()` y, si tiene éxito, `Linking.openURL(resultado.url_autorizacion)` (importar `Linking` de `expo-linking`); si falla, usa `primerMensajeDeError`/el mismo patrón de manejo de `ErrorDeServidor` ya establecido en `perfil/index.tsx` para mostrar `error.body.detail`. Si `donacion_actual` no es `null`, muestra su `estado`/`monto` y un botón "Cancelar" que llama a `cancelarDonacion()` y vuelve a cargar.

- [ ] **Step 8: Correr los tests, confirmar que pasan**

Run: `cd app_movil && npx jest "src/__tests__/app/(vecino)/donar" --watchAll=false`
Expected: PASS, 4/4.

- [ ] **Step 9: Agregar la pantalla al Drawer**

En `app_movil/src/app/(vecino)/_layout.tsx`, agregar `<Drawer.Screen name="donar/index" options={{ title: "Donar" }} />` junto a las demás.

- [ ] **Step 10: Correr el suite completo de Jest**

Run: `cd app_movil && npx jest --watchAll=false`
Expected: PASS, todos los tests (los de antes + los nuevos de esta tarea).

- [ ] **Step 11: Verificación manual de rutas**

Run: `cd app_movil && npx expo start --web` y confirmar que `/donar` sirve 200 sin error, igual que el resto de las rutas de `(vecino)/`.

- [ ] **Step 12: Commit**

```bash
git add app_movil/src/api/donaciones.ts app_movil/src/api/donaciones.test.ts app_movil/src/app/"(vecino)"/donar app_movil/src/__tests__/app/"(vecino)"/donar app_movil/src/app/"(vecino)"/_layout.tsx
git commit -m "feat: pantalla Donar en la app móvil (Tanda 4)"
```

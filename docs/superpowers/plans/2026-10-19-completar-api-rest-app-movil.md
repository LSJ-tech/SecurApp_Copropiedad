# Completar la API REST de Mi Barrio+ (Fase 1 de la app móvil) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exponer vía DRF todo lo que hoy solo existe como vistas HTML y que la futura app móvil necesita (salvo pagos): directorio, miembros/torres/unidades, Mi condominio, invitación/registro de residentes, y condominio activo de devquad sin depender de la sesión web.

**Architecture:** Un `serializers.py`/`api_views.py`/`api_urls.py` por app (mismo patrón que `alertas`/`comunicacion` ya usan), registrados bajo `api/v1/` en `config/urls.py`. Dos estilos de validación, elegidos según el caso:
- **Reusar el Form de Django existente tal cual** (instanciado dentro de la vista DRF, con `data=request.data`) para los flujos de alta/acción completos que ya tienen uno: `CrearMiembroForm`, `MoverMiembroForm`, `RegistroResidenteForm`. Evita duplicar validación no trivial (cruces, `get_or_create`, mensajes de error) en dos lugares.
- **DRF `ModelSerializer`** para lectura y para `PATCH` parcial (`Condominio`), y para los recursos simples sin Form hoy (`Torre`, `Unidad` en create, listados) -- los Forms de Django no soportan `partial=True` ni dan de forma nativa el shape anidado que un cliente JSON necesita.

**Tech Stack:** Django 6.1.2, DRF, SimpleJWT (`rest_framework_simplejwt`, con blacklist).

**Spec:** `docs/superpowers/specs/2026-10-19-completar-api-rest-app-movil-design.md`

## Global Constraints

- Nada de esto modifica una vista HTML existente -- todo es aditivo, en archivos nuevos o agregados al final de los `serializers.py`/`api_views.py`/`api_urls.py` de cada app.
- Todo endpoint nuevo resuelve el condominio vía `condominio_de_la_api` (o su versión extendida por la Tarea 1) -- nunca confía en un `condominio_id` que mande el cliente sin validar.
- Todo endpoint de solo-devquad usa `permission_classes = [IsAuthenticated, EsDevquad, TieneCondominioActivo]` (ambas clases de `core/permissions.py`), igual que `SoloStaffMixin` + `CondominioRequiredMixin` combinados del lado HTML.
- Si una vista sobreescribe `get_permissions()`, comparar contra `self.action`, nunca contra `self.request.method` (bug ya ocurrido con `AvisoViewSet.marcar_leido`).
- TDD: cada endpoint entra con su test en rojo primero. Suite completa (`./venv/Scripts/python.exe manage.py test --keepdb`, ~90-140s, correr en background) en verde antes de cada commit.
- Tests nuevos de `core` van en `core/tests.py` (no se crea un archivo nuevo -- mismo criterio que `alertas/tests.py`, que mezcla tests de vistas HTML y de ViewSets DRF en un solo archivo).
- `python`/`pip` sueltos resuelven al stub roto de Windows -- siempre `./venv/Scripts/python.exe`.

## Review Focus

- Un residente (no delegado, no devquad) pide `GET /api/v1/directorio/` -- debe dar 403, igual que hoy lo bloquea `DirectorioVecinosView.dispatch` ("decisión de producto", no un simple permiso de condominio).
- Se crea/edita una `Unidad` con una `torre` que pertenece a OTRO condominio -- debe rechazarse igual que `Unidad.clean()` ya lo hace del lado HTML/admin (`UnidadSerializer.validate` tiene que replicar esa regla, un `ModelSerializer` no llama `full_clean()` solo).
- Se llama a `MembresiaViewSet.mover` con un `pk` de una Membresia que pertenece a OTRO condominio que el activo -- debe dar 404, igual que `MoverMiembroView.get_miembro` (el pk de la URL no alcanza por sí solo).
- Un devquad JWT (con `condominio_id` en el claim) hace un `/auth/refresh/` -- el access token nuevo tiene que conservar el claim (confirmado como riesgo real en el builder check: `TokenRefreshSerializer` deriva el access del refresh, no hay claim nuevo si no está ya en el refresh que se reemitió).
- El panel web (devquad logueado por sesión, sin JWT) sigue pegándole a estos mismos endpoints nuevos vía `SessionAuthentication` -- `condominio_de_la_api` tiene que seguir resolviendo por sesión en ese caso, no solo por claim de JWT.

---

## File Structure

```
core/
  permissions.py       (modificar: condominio_de_la_api lee claim JWT)
  serializers.py        (agregar: DirectorioMiembroSerializer, CondominioEdicionSerializer,
                          TorreSerializer, UnidadSerializer, MembresiaListSerializer)
  api_views.py           (agregar: DevquadCondominiosApiView, DevquadEntrarCondominioApiView,
                          DirectorioView, CondominioView, RegenerarTokenApiView, InvitacionView,
                          RegistroPublicoView, TorreViewSet, UnidadViewSet, MembresiaViewSet)
  api_urls.py            (agregar rutas + router para los ViewSets nuevos)
  tests.py               (agregar clases de test nuevas al final)
```

No se toca ningún archivo de `pagos/` (non-goal) ni ninguna plantilla/vista HTML.

---

## Nota sobre imports en `core/tests.py`

`core/tests.py` hoy (línea 1-16) no importa nada de `rest_framework_simplejwt`. Las Tareas 1 y 2 son las primeras en usar `AccessToken`/`RefreshToken` -- agregar `from rest_framework_simplejwt.tokens import AccessToken, RefreshToken` junto al resto de imports de terceros (después de `from django.utils.http import urlsafe_base64_encode`, antes de los imports locales `from .forms import ...`) la primera vez que se necesite (Tarea 1), no repetirlo en tareas siguientes.

### Task 1: Condominio activo de devquad vía JWT (D-01, parte A)

**Files:**
- Modify: `core/permissions.py:11-23` (`condominio_de_la_api`)
- Test: `core/tests.py` (nueva clase `CondominioDeLaApiClaimJwtTests`)

**Interfaces:**
- Consumes: nada nuevo (usa `condominio_activo_devquad` ya existente de `core/mixins.py`).
- Produces: `condominio_de_la_api(request)` ahora también resuelve devquad por claim JWT. Las Tareas 2-10 que necesiten "devquad con condominio activo" en sus tests pueden seguir usando el patrón ya existente (`force_login` + `GET devquad-entrar-condominio/<pk>/`, que setea la sesión) -- no dependen de esta tarea para pasar.

- [ ] **Step 1: Escribir el test que falla**

```python
# core/tests.py
class CondominioDeLaApiClaimJwtTests(TestCase):
    def test_devquad_con_claim_condominio_id_en_el_token_resuelve_ese_condominio(self):
        from core.permissions import condominio_de_la_api
        from rest_framework.test import APIRequestFactory
        from rest_framework_simplejwt.tokens import AccessToken

        condominio = Condominio.objects.create(nombre="Test Claim JWT", plan="premium")
        devquad = crear_devquad("claim_jwt_devquad")
        token = AccessToken.for_user(devquad)
        token["condominio_id"] = condominio.pk

        request = APIRequestFactory().get("/")
        request.user = devquad
        request.auth = token
        self.assertEqual(condominio_de_la_api(request), condominio)

    def test_devquad_sin_claim_sigue_resolviendo_por_sesion_web(self):
        """SessionAuthentication (el panel web) no setea request.auth a un
        Token -- tiene que seguir funcionando igual que hoy."""
        from core.permissions import condominio_de_la_api
        from rest_framework.test import APIRequestFactory

        condominio = Condominio.objects.create(nombre="Test Claim Sesion", plan="premium")
        devquad = crear_devquad("claim_sesion_devquad")
        self.client.force_login(devquad)
        self.client.get(reverse("devquad-entrar-condominio", args=[condominio.pk]))

        request = APIRequestFactory().get("/")
        request.user = devquad
        request.auth = None
        request.session = self.client.session
        self.assertEqual(condominio_de_la_api(request), condominio)
```

- [ ] **Step 2: Correr el test, confirmar que falla**

Run: `./venv/Scripts/python.exe manage.py test core.tests.CondominioDeLaApiClaimJwtTests --keepdb -v 2`
Expected: el primer test FALLA (hoy devuelve `None`, no lee ningún claim); el segundo ya pasa (comportamiento sin cambios).

- [ ] **Step 3: Implementar**

En `core/permissions.py`, dentro de `condominio_de_la_api`, antes del fallback a `condominio_activo_devquad`: si `request.user.is_staff` y `getattr(request, "auth", None)` tiene un claim `"condominio_id"` (los tokens de SimpleJWT soportan `token.get("condominio_id")`), resolver `Condominio.objects.filter(pk=...).first()` con ese id; si no hay claim o no hay `request.auth`, seguir con el camino de sesión de siempre. Importar `Condominio` desde `.models` (import ya evitado arriba por ciclo -- usar el mismo patrón de import local dentro de la función que ya usa `condominio_activo_devquad` para `Condominio`).

- [ ] **Step 4: Correr el test, confirmar que pasa**

Run: `./venv/Scripts/python.exe manage.py test core.tests.CondominioDeLaApiClaimJwtTests --keepdb -v 2`
Expected: PASS (2/2)

- [ ] **Step 5: Suite completa + commit**

Run: `./venv/Scripts/python.exe manage.py test --keepdb` (background)
Expected: todos los tests en verde (sin regresiones)

```bash
git add core/permissions.py core/tests.py
git commit -m "feat(api): condominio activo de devquad via claim JWT, ademas de sesion"
```

---

### Task 2: Elegir condominio activo de devquad -- endpoints (D-01, parte B)

**Files:**
- Modify: `core/serializers.py` (reusa `CondominioResumenSerializer`, ya existe -- sin cambios de archivo)
- Modify: `core/api_views.py` (agregar `DevquadCondominiosApiView`, `DevquadEntrarCondominioApiView`)
- Modify: `core/api_urls.py` (agregar las dos rutas)
- Test: `core/tests.py` (nueva clase `DevquadCondominioActivoApiTests`)

**Interfaces:**
- Consumes: Tarea 1 (`condominio_de_la_api` ya entiende el claim que este endpoint produce).
- Produces: `POST /api/v1/devquad/condominios/<id>/entrar/` -- response `{"access": str, "refresh": str, "condominio": {...CondominioResumenSerializer...}}`. Reemite un par access+refresh completo (no solo el access) y blacklistea el refresh recibido -- ver razón en el Spec D-01 y en Review Focus.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# core/tests.py
class DevquadCondominioActivoApiTests(TestCase):
    def test_lista_todos_los_condominios(self):
        Condominio.objects.create(nombre="Test Lista Api A", plan="premium")
        Condominio.objects.create(nombre="Test Lista Api B", plan="premium")
        devquad = crear_devquad("lista_api_devquad")
        self.client.force_login(devquad)
        r = self.client.get(reverse("api-devquad-condominios"))
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.json()), 2)

    def test_un_residente_no_puede_listar(self):
        condominio = Condominio.objects.create(nombre="Test Lista Api Residente", plan="premium")
        residente = crear_membresia(condominio, "residente", username="lista_api_residente")
        self.client.force_login(residente.user)
        r = self.client.get(reverse("api-devquad-condominios"))
        self.assertEqual(r.status_code, 403)

    def test_entrar_devuelve_tokens_nuevos_con_el_condominio_en_el_claim(self):
        from rest_framework_simplejwt.tokens import AccessToken

        condominio = Condominio.objects.create(nombre="Test Entrar Api", plan="premium")
        devquad = crear_devquad("entrar_api_devquad")
        refresh = RefreshToken.for_user(devquad)
        r = self.client.post(
            reverse("api-devquad-entrar-condominio", args=[condominio.pk]),
            {"refresh": str(refresh)}, content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
        )
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        access_nuevo = AccessToken(datos["access"])
        self.assertEqual(access_nuevo["condominio_id"], condominio.pk)
        self.assertEqual(datos["condominio"]["id"], condominio.pk)

    def test_entrar_blacklistea_el_refresh_recibido(self):
        condominio = Condominio.objects.create(nombre="Test Entrar Blacklist", plan="premium")
        devquad = crear_devquad("entrar_blacklist_devquad")
        refresh = RefreshToken.for_user(devquad)
        self.client.post(
            reverse("api-devquad-entrar-condominio", args=[condominio.pk]),
            {"refresh": str(refresh)}, content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}",
        )
        r2 = self.client.post(reverse("api-refresh"), {"refresh": str(refresh)}, content_type="application/json")
        self.assertEqual(r2.status_code, 401)
```

(`RefreshToken` importado arriba del archivo junto al resto de imports de `rest_framework_simplejwt.tokens` si no está ya.)

- [ ] **Step 2: Correr los tests, confirmar que fallan**

Run: `./venv/Scripts/python.exe manage.py test core.tests.DevquadCondominioActivoApiTests --keepdb -v 2`
Expected: FAIL (`NoReverseMatch`, las URLs todavía no existen)

- [ ] **Step 3: Implementar `DevquadCondominiosApiView` y `DevquadEntrarCondominioApiView` en `core/api_views.py`**

`DevquadCondominiosApiView(APIView)`: `permission_classes = [IsAuthenticated, EsDevquad]`; `get` devuelve `Response(CondominioResumenSerializer(Condominio.objects.all().order_by("nombre"), many=True).data)`.

`DevquadEntrarCondominioApiView(APIView)`: `permission_classes = [IsAuthenticated, EsDevquad]`; `post(self, request, pk)`:
1. `condominio = get_object_or_404(Condominio, pk=pk)`.
2. Generar un `RefreshToken.for_user(request.user)` nuevo, setear `refresh["condominio_id"] = condominio.pk` y `refresh.access_token["condominio_id"] = condominio.pk` (el claim tiene que estar en AMBOS para que sobreviva al próximo refresh, ver Review Focus).
3. Blacklistear el refresh recibido en `request.data["refresh"]` (mismo patrón que `LogoutView`, `try/except (KeyError, TokenError)` -> 400 si falta o es inválido).
4. `return Response({"access": str(refresh.access_token), "refresh": str(refresh), "condominio": CondominioResumenSerializer(condominio).data})`.

- [ ] **Step 4: Agregar las rutas en `core/api_urls.py`**

```python
path("devquad/condominios/", api_views.DevquadCondominiosApiView.as_view(), name="api-devquad-condominios"),
path("devquad/condominios/<int:pk>/entrar/", api_views.DevquadEntrarCondominioApiView.as_view(), name="api-devquad-entrar-condominio"),
```

- [ ] **Step 5: Correr los tests, confirmar que pasan**

Run: `./venv/Scripts/python.exe manage.py test core.tests.DevquadCondominioActivoApiTests --keepdb -v 2`
Expected: PASS (4/4)

- [ ] **Step 6: Suite completa + commit**

```bash
git add core/api_views.py core/api_urls.py core/tests.py
git commit -m "feat(api): devquad elige condominio activo via API (lista + entrar)"
```

---

### Task 3: Directorio de vecinos (D-02)

**Files:**
- Modify: `core/serializers.py` (agregar `DirectorioMiembroSerializer`)
- Modify: `core/api_views.py` (agregar `DirectorioView`)
- Modify: `core/api_urls.py` (agregar ruta)
- Test: `core/tests.py` (nueva clase `DirectorioApiTests`)

**Interfaces:**
- Produces: `GET /api/v1/directorio/` -> `[{"nombre": str, "torre": str|null, "unidad": str|null}, ...]`, ordenado igual que `DirectorioVecinosView` (`unidad__torre__nombre`, `unidad__numero`, `user__last_name`, usando el mismo criterio de orden natural -- ver `_torre_len`/`_num_len` del resto del proyecto).

- [ ] **Step 1: Escribir los tests que fallan**

```python
# core/tests.py
class DirectorioApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Directorio Api", plan="premium")

    def test_un_residente_no_puede_ver_el_directorio(self):
        unidad = Unidad.objects.create(condominio=self.condominio, numero="1")
        residente = crear_membresia(self.condominio, "residente", unidad=unidad, username="dir_api_residente")
        self.client.force_login(residente.user)
        r = self.client.get(reverse("api-directorio"))
        self.assertEqual(r.status_code, 403)

    def test_un_delegado_ve_nombre_torre_y_unidad(self):
        torre = Torre.objects.create(condominio=self.condominio, nombre="1")
        unidad = Unidad.objects.create(condominio=self.condominio, torre=torre, numero="101")
        vecino = crear_membresia(self.condominio, "residente", unidad=unidad, username="dir_api_vecino", first_name="Ana", last_name="Soto")
        delegado = crear_membresia(self.condominio, "delegado", unidad=unidad, username="dir_api_delegado")
        self.client.force_login(delegado.user)
        r = self.client.get(reverse("api-directorio"))
        self.assertEqual(r.status_code, 200)
        fila = next(f for f in r.json() if f["nombre"] == "Ana Soto")
        self.assertEqual(fila["torre"], "1")
        self.assertEqual(fila["unidad"], "101")
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `./venv/Scripts/python.exe manage.py test core.tests.DirectorioApiTests --keepdb -v 2`
Expected: FAIL (`NoReverseMatch`)

- [ ] **Step 3: Implementar**

`DirectorioMiembroSerializer(serializers.Serializer)` (no ModelSerializer -- el shape no calza 1:1 con ningún modelo): `nombre = SerializerMethodField()`, `torre = CharField(source="unidad.torre.nombre", default=None)`, `unidad = SerializerMethodField()`. `get_nombre`: `obj.user.get_full_name() or "Vecino/a"` (mismo fallback que el template). `get_unidad`: si `obj.unidad_id` es `None` -> `None`; si no, `f"{obj.unidad.calle} {obj.unidad.numero}".strip()` si `obj.unidad.calle` si no `obj.unidad.numero`.

`DirectorioView(APIView)`: `permission_classes = [IsAuthenticated, EsDevquadODelegado, TieneCondominioActivo]`. `get`: resolver `condominio = condominio_de_la_api(request)`, `qs = Membresia.objects.filter(condominio=condominio).select_related("user","unidad","unidad__torre").annotate(_torre_len=Length("unidad__torre__nombre"), _num_len=Length("unidad__numero")).order_by("_torre_len","unidad__torre__nombre","_num_len","unidad__numero","user__last_name")`, devolver `Response(DirectorioMiembroSerializer(qs, many=True).data)`.

- [ ] **Step 4: Agregar la ruta**

```python
path("directorio/", api_views.DirectorioView.as_view(), name="api-directorio"),
```

- [ ] **Step 5: Correr, confirmar que pasan**

Run: `./venv/Scripts/python.exe manage.py test core.tests.DirectorioApiTests --keepdb -v 2`
Expected: PASS (2/2)

- [ ] **Step 6: Suite completa + commit**

```bash
git add core/serializers.py core/api_views.py core/api_urls.py core/tests.py
git commit -m "feat(api): directorio de vecinos (solo lectura, delegado+devquad)"
```

---

### Task 4: Mi condominio -- ver/editar + regenerar link (D-04)

**Files:**
- Modify: `core/serializers.py` (agregar `CondominioEdicionSerializer`)
- Modify: `core/api_views.py` (agregar `CondominioView`, `RegenerarTokenApiView`)
- Modify: `core/api_urls.py` (agregar rutas)
- Test: `core/tests.py` (nueva clase `CondominioApiTests`)

**Interfaces:**
- Produces: `GET/PATCH /api/v1/condominio/` (campos: `nombre`, `etiqueta_organizacion`, `direccion`, `comuna`, `region`, `datos_transferencia`, `etiqueta_torre`, `etiqueta_unidad`, `genero_unidad` -- idénticos a `CondominioForm.Meta.fields`). `POST /api/v1/condominio/regenerar-token/` -> `{"token_registro_residentes": str}`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# core/tests.py
class CondominioApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(
            nombre="Test Condominio Api", plan="premium", direccion="Calle Vieja 1", comuna="Valparaíso", region="valparaiso",
        )

    def _login_devquad(self):
        devquad = crear_devquad("condominio_api_devquad")
        self.client.force_login(devquad)
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))

    def test_get_devuelve_los_datos_actuales(self):
        self._login_devquad()
        r = self.client.get(reverse("api-condominio"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["direccion"], "Calle Vieja 1")

    def test_patch_actualiza_solo_los_campos_mandados(self):
        self._login_devquad()
        r = self.client.patch(reverse("api-condominio"), {"direccion": "Calle Nueva 2"}, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.condominio.refresh_from_db()
        self.assertEqual(self.condominio.direccion, "Calle Nueva 2")
        self.assertEqual(self.condominio.nombre, "Test Condominio Api")  # no se tocó

    def test_patch_con_comuna_que_no_calza_con_la_region_es_invalido(self):
        self._login_devquad()
        r = self.client.patch(
            reverse("api-condominio"), {"region": "valparaiso", "comuna": "Providencia"}, content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        self.condominio.refresh_from_db()
        self.assertEqual(self.condominio.comuna, "Valparaíso")  # no se tocó

    def test_un_residente_no_puede_ver_ni_editar(self):
        unidad = Unidad.objects.create(condominio=self.condominio, numero="1")
        residente = crear_membresia(self.condominio, "residente", unidad=unidad, username="condominio_api_residente")
        self.client.force_login(residente.user)
        r = self.client.get(reverse("api-condominio"))
        self.assertEqual(r.status_code, 403)

    def test_regenerar_token_cambia_el_token(self):
        self._login_devquad()
        token_anterior = self.condominio.token_registro_residentes
        r = self.client.post(reverse("api-regenerar-token"))
        self.assertEqual(r.status_code, 200)
        self.condominio.refresh_from_db()
        self.assertNotEqual(self.condominio.token_registro_residentes, token_anterior)
        self.assertEqual(r.json()["token_registro_residentes"], self.condominio.token_registro_residentes)
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `./venv/Scripts/python.exe manage.py test core.tests.CondominioApiTests --keepdb -v 2`
Expected: FAIL (`NoReverseMatch`)

- [ ] **Step 3: Implementar**

`CondominioEdicionSerializer(serializers.ModelSerializer)`: `Meta.model = Condominio`, `fields = ["nombre","etiqueta_organizacion","direccion","comuna","region","datos_transferencia","etiqueta_torre","etiqueta_unidad","genero_unidad"]`. `validate(self, attrs)`: misma regla que `RegionComunaMixin.clean()` -- tomar `region`/`comuna` de `attrs` (si no vienen en un PATCH parcial, usar `getattr(self.instance, campo)` como fallback) y, si ambos están presentes y `comuna not in COMUNAS_POR_REGION.get(region, [])`, `raise serializers.ValidationError({"comuna": "Esa comuna no pertenece a la región elegida."})`.

`CondominioView(APIView)`: `permission_classes = [IsAuthenticated, EsDevquad, TieneCondominioActivo]`. `get`: `Response(CondominioEdicionSerializer(condominio_de_la_api(request)).data)`. `patch`: `serializer = CondominioEdicionSerializer(condominio_de_la_api(request), data=request.data, partial=True)`, `serializer.is_valid(raise_exception=True)`, `serializer.save()`, `Response(serializer.data)`.

`RegenerarTokenApiView(APIView)`: mismo permiso. `post`: `condominio = condominio_de_la_api(request)`, `condominio.token_registro_residentes = generar_codigo_invitacion()`, `condominio.save(update_fields=["token_registro_residentes"])`, `Response({"token_registro_residentes": condominio.token_registro_residentes})`. (Importar `generar_codigo_invitacion` de `.usuarios`, ya se importa en `core/views.py` -- agregar el mismo import en `core/api_views.py`.)

- [ ] **Step 4: Agregar las rutas**

```python
path("condominio/", api_views.CondominioView.as_view(), name="api-condominio"),
path("condominio/regenerar-token/", api_views.RegenerarTokenApiView.as_view(), name="api-regenerar-token"),
```

- [ ] **Step 5: Correr, confirmar que pasan**

Run: `./venv/Scripts/python.exe manage.py test core.tests.CondominioApiTests --keepdb -v 2`
Expected: PASS (6/6)

- [ ] **Step 6: Suite completa + commit**

```bash
git add core/serializers.py core/api_views.py core/api_urls.py core/tests.py
git commit -m "feat(api): ver/editar Mi condominio y regenerar link de invitacion"
```

---

### Task 5: Invitación y autoregistro público (D-05)

**Files:**
- Modify: `core/api_views.py` (agregar `InvitacionView`, `RegistroPublicoView`)
- Modify: `core/api_urls.py` (agregar rutas)
- Test: `core/tests.py` (nuevas clases `InvitacionApiTests`, `RegistroPublicoApiTests`)

**Interfaces:**
- Consumes: `_contexto_invitacion` (`core/views.py:423`), `RegistroResidenteForm` (`core/forms.py:174`), `enviar_correo_bienvenida` (`core/views.py:43`), `generar_username` (`core/usuarios.py`), `CustomTokenObtainPairSerializer`/`MembresiaSerializer` (`core/serializers.py`) -- todos ya existentes, sin cambios.
- Produces: `GET /api/v1/invitacion/` -> `{"link": str, "mensaje": str}` (cualquier miembro autenticado). `GET /api/v1/registro/<token>/` -> `{"condominio": {...}, "torres": [...], "unidades": [...], "modo_casas": bool}` (público). `POST /api/v1/registro/<token>/` -> `{"username": str, "access": str, "refresh": str, "membresia": {...}}` (público, crea la cuenta).

- [ ] **Step 1: Escribir los tests que fallan**

```python
# core/tests.py
class InvitacionApiTests(TestCase):
    def test_devuelve_el_link_y_el_mensaje(self):
        condominio = Condominio.objects.create(nombre="Test Invitacion Api", plan="premium")
        unidad = Unidad.objects.create(condominio=condominio, numero="1")
        residente = crear_membresia(condominio, "residente", unidad=unidad, username="invitacion_api_residente")
        self.client.force_login(residente.user)
        r = self.client.get(reverse("api-invitacion"))
        self.assertEqual(r.status_code, 200)
        self.assertIn(condominio.token_registro_residentes, r.json()["link"])


class RegistroPublicoApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Registro Publico Api", plan="premium")
        cls.torre = Torre.objects.create(condominio=cls.condominio, nombre="1")
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, torre=cls.torre, numero="101")

    def test_get_devuelve_las_unidades_disponibles(self):
        r = self.client.get(reverse("api-registro", args=[self.condominio.token_registro_residentes]))
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        self.assertEqual(datos["condominio"]["nombre"], "Test Registro Publico Api")
        self.assertEqual(len(datos["unidades"]), 1)

    def test_token_invalido_da_404(self):
        r = self.client.get(reverse("api-registro", args=["token-que-no-existe"]))
        self.assertEqual(r.status_code, 404)

    def test_post_crea_la_cuenta_y_devuelve_tokens(self):
        r = self.client.post(
            reverse("api-registro", args=[self.condominio.token_registro_residentes]),
            {
                "nombre": "Pedro", "apellido": "Pérez", "email": "pedro.registro.api@example.com",
                "unidad": self.unidad.pk, "password1": "ClaveSegura123", "password2": "ClaveSegura123",
                "acepto_terminos": True,
            },
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201)
        datos = r.json()
        self.assertTrue(datos["access"])
        membresia = Membresia.objects.get(user__username=datos["username"])
        self.assertEqual(membresia.condominio, self.condominio)
        self.assertEqual(membresia.unidad, self.unidad)

    def test_post_con_datos_invalidos_devuelve_400(self):
        r = self.client.post(
            reverse("api-registro", args=[self.condominio.token_registro_residentes]),
            {"nombre": "Pedro"}, content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `./venv/Scripts/python.exe manage.py test core.tests.InvitacionApiTests core.tests.RegistroPublicoApiTests --keepdb -v 2`
Expected: FAIL (`NoReverseMatch`)

- [ ] **Step 3: Implementar `InvitacionView`**

`permission_classes = [IsAuthenticated, TieneCondominioActivo]`. `get`: `condominio = condominio_de_la_api(request)`, `contexto = _contexto_invitacion(request, condominio)` (ya devuelve un dict con `link`/`mensaje`, ver `core/views.py:423-449` -- confirmar las claves exactas del dict al leerlo), `Response(contexto)`.

- [ ] **Step 4: Implementar `RegistroPublicoView`**

`permission_classes = []`, `authentication_classes = []` (público). `dispatch` o `get`/`post` ambos arrancan con `condominio = get_object_or_404(Condominio, token_registro_residentes=token)`.

`get(self, request, token)`: construir la misma info que `RegistroResidenteView.get_context_data` (torres, unidades agrupadas, modo_casas) pero como JSON serializable a mano (listas de dicts `{"id":, "nombre":}` para torres, `{"id":, "numero":, "torre_id":}` para unidades) -- no se reusa el método de la vista HTML porque arma contexto para un template (`QuerySet`s, no estructuras serializables), se reimplementa la consulta directo (mismas queries, mismo `annotate`/`order_by` que `core/views.py:364-371`).

`post(self, request, token)`: `form = RegistroResidenteForm(data=request.data, condominio=condominio)`; si `not form.is_valid()`: `Response(form.errors, status=400)`; si válido, mismo cuerpo que `RegistroResidenteView.form_valid` (`core/views.py:400-412`) -- crear `User` + `Membresia`, enviar correo de bienvenida si hay email -- pero en vez de `login(request, user, ...)` (sesión), generar tokens: `refresh = RefreshToken.for_user(user)`, `Response({"username": username, "access": str(refresh.access_token), "refresh": str(refresh), "membresia": MembresiaSerializer(membresia).data}, status=201)`.

- [ ] **Step 5: Agregar las rutas**

```python
path("invitacion/", api_views.InvitacionView.as_view(), name="api-invitacion"),
path("registro/<str:token>/", api_views.RegistroPublicoView.as_view(), name="api-registro"),
```

- [ ] **Step 6: Correr, confirmar que pasan**

Run: `./venv/Scripts/python.exe manage.py test core.tests.InvitacionApiTests core.tests.RegistroPublicoApiTests --keepdb -v 2`
Expected: PASS (5/5)

- [ ] **Step 7: Suite completa + commit**

```bash
git add core/api_views.py core/api_urls.py core/tests.py
git commit -m "feat(api): invitacion y autoregistro publico de residentes"
```

---

### Task 6: Torres (D-03, parte 1 de 3)

**Files:**
- Modify: `core/serializers.py` (agregar `TorreSerializer`)
- Modify: `core/api_views.py` (agregar `TorreViewSet`)
- Modify: `core/api_urls.py` (agregar router + registro `"torres"`)
- Test: `core/tests.py` (nueva clase `TorreApiTests`)

**Interfaces:**
- Produces: `GET/POST /api/v1/torres/` -- `TorreSerializer` (`id`, `nombre`), basename `"torre"`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# core/tests.py
class TorreApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Torre Api", plan="premium")

    def _login_devquad(self):
        devquad = crear_devquad("torre_api_devquad")
        self.client.force_login(devquad)
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))

    def test_lista_solo_las_torres_del_condominio_activo(self):
        Torre.objects.create(condominio=self.condominio, nombre="1")
        otro = Condominio.objects.create(nombre="Test Torre Api Otro", plan="premium")
        Torre.objects.create(condominio=otro, nombre="Ajena")
        self._login_devquad()
        r = self.client.get(reverse("torre-list"))
        self.assertEqual(r.status_code, 200)
        nombres = [t["nombre"] for t in r.json()["results"]] if isinstance(r.json(), dict) else [t["nombre"] for t in r.json()]
        self.assertEqual(nombres, ["1"])

    def test_crear_una_torre(self):
        self._login_devquad()
        r = self.client.post(reverse("torre-list"), {"nombre": "2"}, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(Torre.objects.filter(condominio=self.condominio, nombre="2").exists())

    def test_un_residente_no_puede_crear(self):
        unidad = Unidad.objects.create(condominio=self.condominio, numero="1")
        residente = crear_membresia(self.condominio, "residente", unidad=unidad, username="torre_api_residente")
        self.client.force_login(residente.user)
        r = self.client.post(reverse("torre-list"), {"nombre": "3"}, content_type="application/json")
        self.assertEqual(r.status_code, 403)
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `./venv/Scripts/python.exe manage.py test core.tests.TorreApiTests --keepdb -v 2`
Expected: FAIL (`NoReverseMatch`)

- [ ] **Step 3: Implementar**

`TorreSerializer(serializers.ModelSerializer)`: `Meta.model = Torre`, `fields = ["id", "nombre"]`.

`TorreViewSet(CondominioQuerysetMixin, viewsets.ModelViewSet)`: `queryset = Torre.objects.all()`, `serializer_class = TorreSerializer`, `permission_classes = [IsAuthenticated, EsDevquad, TieneCondominioActivo]`, `http_method_names = ["get", "post", "head", "options"]`. `perform_create(self, serializer)`: `serializer.save(condominio=condominio_de_la_api(self.request))` (mismo patrón que `CondominioFormMixin.form_valid` del lado HTML).

- [ ] **Step 4: Agregar el router en `core/api_urls.py`**

```python
from rest_framework.routers import DefaultRouter
router = DefaultRouter()
router.register("torres", api_views.TorreViewSet, basename="torre")
urlpatterns = [...] + router.urls
```

- [ ] **Step 5: Correr, confirmar que pasan**

Run: `./venv/Scripts/python.exe manage.py test core.tests.TorreApiTests --keepdb -v 2`
Expected: PASS (3/3)

- [ ] **Step 6: Suite completa + commit**

```bash
git add core/serializers.py core/api_views.py core/api_urls.py core/tests.py
git commit -m "feat(api): listar/crear torres"
```

---

### Task 7: Unidades (D-03, parte 2 de 3)

**Files:**
- Modify: `core/serializers.py` (agregar `UnidadSerializer`)
- Modify: `core/api_views.py` (agregar `UnidadViewSet`)
- Modify: `core/api_urls.py` (registrar `"unidades"` en el router de la Tarea 6)
- Test: `core/tests.py` (nueva clase `UnidadApiTests`)

**Interfaces:**
- Consumes: router de la Tarea 6 (mismo archivo `core/api_urls.py`).
- Produces: `GET/POST /api/v1/unidades/` -- `UnidadSerializer` (`id`, `numero`, `calle`, `torre`, `alicuota`), basename `"unidad"`. Paginado (`PageNumberPagination`, `page_size=50`) -- primer caso de D-07.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# core/tests.py
class UnidadApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Unidad Api", plan="premium")
        cls.torre = Torre.objects.create(condominio=cls.condominio, nombre="1")

    def _login_devquad(self):
        devquad = crear_devquad("unidad_api_devquad")
        self.client.force_login(devquad)
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))

    def test_crear_una_unidad(self):
        self._login_devquad()
        r = self.client.post(
            reverse("unidad-list"), {"numero": "101", "torre": self.torre.pk, "calle": "", "alicuota": "0"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertTrue(Unidad.objects.filter(condominio=self.condominio, numero="101").exists())

    def test_una_torre_de_otro_condominio_es_invalida(self):
        otro = Condominio.objects.create(nombre="Test Unidad Api Otro", plan="premium")
        torre_ajena = Torre.objects.create(condominio=otro, nombre="Ajena")
        self._login_devquad()
        r = self.client.post(
            reverse("unidad-list"), {"numero": "102", "torre": torre_ajena.pk}, content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Unidad.objects.filter(numero="102").exists())

    def test_lista_paginada(self):
        for i in range(55):
            Unidad.objects.create(condominio=self.condominio, numero=str(i))
        self._login_devquad()
        r = self.client.get(reverse("unidad-list"))
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        self.assertIn("results", datos)
        self.assertEqual(len(datos["results"]), 50)
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `./venv/Scripts/python.exe manage.py test core.tests.UnidadApiTests --keepdb -v 2`
Expected: FAIL (`NoReverseMatch`)

- [ ] **Step 3: Implementar**

`UnidadSerializer(serializers.ModelSerializer)`: `Meta.model = Unidad`, `fields = ["id", "numero", "calle", "torre", "alicuota"]`. `validate(self, attrs)`: replicar `Unidad.clean()` -- si `attrs.get("torre")` está presente y el `condominio` de esa torre no es el `condominio_de_la_api(self.context["request"])`, `raise serializers.ValidationError({"torre": "Esa torre pertenece a otro condominio."})`.

`UnidadViewSet(CondominioQuerysetMixin, viewsets.ModelViewSet)`: `queryset = Unidad.objects.select_related("torre")`, `serializer_class = UnidadSerializer`, `permission_classes = [IsAuthenticated, EsDevquad, TieneCondominioActivo]`, `http_method_names = ["get", "post", "head", "options"]`, `pagination_class = rest_framework.pagination.PageNumberPagination` con `page_size = 50` (definir una subclase chica `class PaginacionUnidades(PageNumberPagination): page_size = 50` arriba del ViewSet, o setear el atributo directo en settings-less style -- cualquiera de las dos sirve, elegir la subclase para no tocar `DEFAULT_PAGINATION_CLASS` global, ver D-07). `get_serializer_context()` ya incluye `request` por defecto en DRF (no hace falta sobreescribirlo) -- el `validate` de arriba lo necesita para `condominio_de_la_api`. `perform_create`: `serializer.save(condominio=condominio_de_la_api(self.request))`.

- [ ] **Step 4: Registrar en el router**

```python
router.register("unidades", api_views.UnidadViewSet, basename="unidad")
```

- [ ] **Step 5: Correr, confirmar que pasan**

Run: `./venv/Scripts/python.exe manage.py test core.tests.UnidadApiTests --keepdb -v 2`
Expected: PASS (3/3)

- [ ] **Step 6: Suite completa + commit**

```bash
git add core/serializers.py core/api_views.py core/api_urls.py core/tests.py
git commit -m "feat(api): listar/crear unidades, paginado y con torre validada"
```

---

### Task 8: Miembros -- listar y crear (D-03, parte 3 de 3)

**Files:**
- Modify: `core/serializers.py` (agregar `MembresiaListSerializer`)
- Modify: `core/api_views.py` (agregar `MembresiaViewSet`, con `list`+`create` -- `mover` llega en la Tarea 9)
- Modify: `core/api_urls.py` (registrar `"miembros"` en el router)
- Test: `core/tests.py` (nueva clase `MembresiaApiTests`)

**Interfaces:**
- Consumes: `CrearMiembroForm` (`core/forms.py:107`), `generar_username`/`generar_password_temporal` (`core/usuarios.py`), `enviar_correo_bienvenida` (`core/views.py:43`).
- Produces: `GET /api/v1/miembros/` -- paginado (`page_size=50`, mismo criterio que la Tarea 7), `MembresiaListSerializer` (`id`, `nombre`, `rol`, `rol_display`, `unidad_numero`, `unidad_torre`). `POST /api/v1/miembros/` -> body `{nombre, apellido, email, rol, unidad}` (mismos campos que `CrearMiembroForm`) -> `201 {"id": int, "username": str, "password_temporal": str}` o `400 {<errores del form>}`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# core/tests.py
class MembresiaApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Membresia Api", plan="premium")
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, numero="1")

    def _login_devquad(self):
        devquad = crear_devquad("membresia_api_devquad")
        self.client.force_login(devquad)
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))

    def test_lista_los_miembros_del_condominio_activo(self):
        crear_membresia(self.condominio, "residente", unidad=self.unidad, username="membresia_api_vecino", first_name="Rosa", last_name="Diaz")
        self._login_devquad()
        r = self.client.get(reverse("membresia-list"))
        self.assertEqual(r.status_code, 200)
        datos = r.json()["results"]
        fila = next(f for f in datos if f["nombre"] == "Rosa Diaz")
        self.assertEqual(fila["unidad_numero"], "1")

    def test_crear_un_miembro_nuevo(self):
        self._login_devquad()
        r = self.client.post(
            reverse("membresia-list"),
            {"nombre": "Luis", "apellido": "Rojas", "email": "luis.membresia.api@example.com", "rol": "residente", "unidad": self.unidad.pk},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201)
        datos = r.json()
        self.assertTrue(datos["password_temporal"])
        membresia = Membresia.objects.get(pk=datos["id"])
        self.assertEqual(membresia.condominio, self.condominio)
        self.assertEqual(membresia.unidad, self.unidad)

    def test_crear_residente_sin_unidad_da_400(self):
        self._login_devquad()
        r = self.client.post(
            reverse("membresia-list"),
            {"nombre": "Luis", "apellido": "Rojas", "email": "luis2.membresia.api@example.com", "rol": "residente"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)

    def test_un_residente_no_puede_listar_ni_crear(self):
        residente = crear_membresia(self.condominio, "residente", unidad=self.unidad, username="membresia_api_residente")
        self.client.force_login(residente.user)
        r = self.client.get(reverse("membresia-list"))
        self.assertEqual(r.status_code, 403)
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `./venv/Scripts/python.exe manage.py test core.tests.MembresiaApiTests --keepdb -v 2`
Expected: FAIL (`NoReverseMatch`)

- [ ] **Step 3: Implementar**

`MembresiaListSerializer(serializers.ModelSerializer)`: `nombre = SerializerMethodField()`, `rol_display = CharField(source="get_rol_display", read_only=True)`, `unidad_numero = CharField(source="unidad.numero", read_only=True, default=None)`, `unidad_torre = CharField(source="unidad.torre.nombre", read_only=True, default=None)`. `Meta.model = Membresia`, `fields = ["id", "nombre", "rol", "rol_display", "unidad_numero", "unidad_torre"]`. `get_nombre(self, obj)`: `obj.user.get_full_name() or obj.user.username`.

`MembresiaViewSet(viewsets.GenericViewSet, mixins.ListModelMixin)`: `serializer_class = MembresiaListSerializer`, `permission_classes = [IsAuthenticated, EsDevquad, TieneCondominioActivo]`, `pagination_class` = la misma subclase de paginación de la Tarea 7 (moverla a un lugar compartido en `core/api_views.py`, ej. `PaginacionEstandar`, y reusarla en `UnidadViewSet` también -- pequeño ajuste a la Tarea 7 al pasar por acá, sin cambiar su comportamiento). `get_queryset(self)`: `Membresia.objects.filter(condominio=condominio_de_la_api(self.request)).select_related("user", "unidad", "unidad__torre")`.

`create(self, request, *args, **kwargs)` (override completo, no se usa `CreateModelMixin` porque el shape de entrada/salida no es el modelo `Membresia` directo): `condominio = condominio_de_la_api(request)`; `form = CrearMiembroForm(data=request.data, condominio=condominio)`; si inválido, `Response(form.errors, status=400)`; si válido, mismo cuerpo que `CrearMiembroView.form_valid` (`core/views.py:799-819`, sin los `messages.success` ni el redirect): generar `username`/`password` temporal, crear `User`+`Membresia` dentro de `transaction.atomic()`, enviar correo de bienvenida si hay email, `Response({"id": membresia.pk, "username": username, "password_temporal": password}, status=201)`.

- [ ] **Step 4: Registrar en el router**

```python
router.register("miembros", api_views.MembresiaViewSet, basename="membresia")
```

- [ ] **Step 5: Correr, confirmar que pasan**

Run: `./venv/Scripts/python.exe manage.py test core.tests.MembresiaApiTests --keepdb -v 2`
Expected: PASS (4/4)

- [ ] **Step 6: Suite completa + commit**

```bash
git add core/serializers.py core/api_views.py core/api_urls.py core/tests.py
git commit -m "feat(api): listar miembros y crear una cuenta nueva"
```

---

### Task 9: Mover un miembro de condominio (D-03, acción `mover`)

**Files:**
- Modify: `core/api_views.py` (agregar la acción `mover` a `MembresiaViewSet`)
- Test: `core/tests.py` (nueva clase `MoverMiembroApiTests`)

**Interfaces:**
- Consumes: `MembresiaViewSet` (Tarea 8), `MoverMiembroForm` (`core/forms.py:143`).
- Produces: `PATCH /api/v1/miembros/<pk>/mover/` -> body `{condominio_destino, unidad_destino}` -> `200 MembresiaListSerializer` actualizado, o `400`/`404`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# core/tests.py
class MoverMiembroApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.origen = Condominio.objects.create(nombre="Test Mover Api Origen", plan="premium")
        cls.destino = Condominio.objects.create(nombre="Test Mover Api Destino", plan="premium")
        cls.unidad_origen = Unidad.objects.create(condominio=cls.origen, numero="1")
        cls.unidad_destino = Unidad.objects.create(condominio=cls.destino, numero="101")

    def setUp(self):
        self.miembro = crear_membresia(self.origen, "residente", unidad=self.unidad_origen, username="mover_api_residente")
        self.client.force_login(crear_devquad("mover_api_devquad"))
        self.client.get(reverse("devquad-entrar-condominio", args=[self.origen.pk]))

    def test_mueve_la_membresia_sin_crear_una_nueva(self):
        r = self.client.patch(
            reverse("membresia-mover", args=[self.miembro.pk]),
            {"condominio_destino": self.destino.pk, "unidad_destino": self.unidad_destino.pk},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.miembro.refresh_from_db()
        self.assertEqual(self.miembro.condominio, self.destino)
        self.assertEqual(self.miembro.unidad, self.unidad_destino)
        self.assertEqual(Membresia.objects.filter(user=self.miembro.user).count(), 1)

    def test_unidad_que_no_es_del_condominio_destino_da_400(self):
        tercero = Condominio.objects.create(nombre="Test Mover Api Tercero", plan="premium")
        unidad_tercero = Unidad.objects.create(condominio=tercero, numero="9")
        r = self.client.patch(
            reverse("membresia-mover", args=[self.miembro.pk]),
            {"condominio_destino": self.destino.pk, "unidad_destino": unidad_tercero.pk},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)

    def test_miembro_de_otro_condominio_da_404(self):
        otro = Condominio.objects.create(nombre="Test Mover Api Ajeno", plan="premium")
        ajeno = crear_membresia(otro, "residente", username="mover_api_ajeno")
        r = self.client.patch(
            reverse("membresia-mover", args=[ajeno.pk]),
            {"condominio_destino": self.destino.pk, "unidad_destino": self.unidad_destino.pk},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 404)
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `./venv/Scripts/python.exe manage.py test core.tests.MoverMiembroApiTests --keepdb -v 2`
Expected: FAIL (`NoReverseMatch`)

- [ ] **Step 3: Implementar**

Agregar a `MembresiaViewSet`:

```python
@action(detail=True, methods=["patch"])
def mover(self, request, pk=None):
    condominio = condominio_de_la_api(request)
    miembro = get_object_or_404(Membresia, pk=pk, condominio=condominio)
    form = MoverMiembroForm(data=request.data, condominio_actual=condominio)
    if not form.is_valid():
        return Response(form.errors, status=400)
    with transaction.atomic():
        miembro.condominio = form.cleaned_data["condominio_destino"]
        miembro.unidad = form.cleaned_data["unidad_destino"]
        miembro.save(update_fields=["condominio", "unidad"])
    return Response(MembresiaListSerializer(miembro).data)
```

(Mismo cuerpo que `MoverMiembroView.form_valid`, `core/views.py:852-863`, sin el `messages.success`. El 404 lo da `get_object_or_404` filtrando por `condominio=condominio` -- el pk de la URL no alcanza solo, igual que la vista HTML.)

- [ ] **Step 4: Correr, confirmar que pasan**

Run: `./venv/Scripts/python.exe manage.py test core.tests.MoverMiembroApiTests --keepdb -v 2`
Expected: PASS (3/3)

- [ ] **Step 5: Suite completa + commit**

```bash
git add core/api_views.py core/tests.py
git commit -m "feat(api): mover un miembro a otro condominio (accion mover)"
```

---

## Self-Review (hecho al escribir este plan)

**Cobertura del spec:** D-01 (Tareas 1-2), D-02 (Tarea 3), D-03 (Tareas 6-9), D-04 (Tarea 4), D-05 (Tarea 5), D-06 (reuso de `EsDevquad`/`TieneCondominioActivo` en todas las tareas, sin clase nueva), D-07 (paginación local en `UnidadViewSet`/`MembresiaViewSet`, Tareas 7-8, sin tocar `DEFAULT_PAGINATION_CLASS`). Non-goals (pagos, la app en sí, cuentas de tienda) no tienen tarea, a propósito.

**Review Focus:** los 5 puntos del header tienen test propio -- directorio bloqueado a residente (Tarea 3), torre de otro condominio rechazada (Tarea 7), mover a un miembro ajeno da 404 (Tarea 9), el claim sobrevive al refresh (Tarea 2, `test_entrar_devuelve_tokens_nuevos_con_el_condominio_en_el_claim` verifica el `access` nuevo, no el viejo), sesión web sigue funcionando (Tarea 1, segundo test).

**Orden:** Tareas 1-2 (D-01) van primero por ser la base de autenticación de devquad para la app, pero ninguna tarea depende de ellas para que sus propios tests pasen (todas usan `force_login` + `devquad-entrar-condominio` para simular sesión, igual que el resto del proyecto ya hace). Tareas 3-9 son independientes entre sí salvo 6->7->8->9 (comparten el mismo router y, desde la Tarea 7, la misma clase de paginación).

---

## Qué queda a criterio de quien lo construya

- Nombre exacto de la subclase de paginación compartida (`PaginacionEstandar` es una sugerencia).
- Mensajes de error exactos cuando un `ModelSerializer` falla validación (usar los que DRF genera por defecto, salvo donde el plan pide un mensaje específico).

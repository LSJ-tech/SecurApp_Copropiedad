# Agregar teléfono al perfil del residente Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capturar y editar un número de teléfono para cada residente/delegado -- hoy no existe en ningún lado del sistema salvo en el formulario de leads (`SolicitudAcceso`).

**Architecture:** `telefono` vive en `Membresia` (no en `User`, que es el modelo propio de Django y no se extiende sin una migración de `AUTH_USER_MODEL` -- cambio mucho más grande e innecesario acá). Se captura en el autoregistro público (web y API, mismo `RegistroResidenteForm`) y se edita después en "Mi perfil" (web y API) agregando el campo a los formularios/serializers existentes, no creando nuevos.

**Tech Stack:** Django 6.1.2, DRF -- mismo stack que el resto del proyecto, sin dependencias nuevas.

**Spec:** `docs/superpowers/specs/2026-10-19-app-movil-mi-barrio-design.md` (Goals: "Agregar `telefono` al perfil del residente"); contexto adicional en `docs/superpowers/specs/2026-10-19-panel-institucional-design.md` (Constraints: por qué hace falta -- prerrequisito de la Fase 3).

## Global Constraints

- `telefono` es opcional (`blank=True`) -- no se backfillea nada para los miembros ya existentes, nadie queda bloqueado por no tenerlo cargado.
- Mismo patrón en los dos caminos (web HTML y API JSON) -- los tests de cada uno verifican el mismo comportamiento, no uno más permisivo que el otro.
- TDD: cada cambio entra con su test en rojo primero. Suite completa (`./venv/Scripts/python.exe manage.py test --keepdb`, en background) en verde antes de cada commit.
- `python`/`pip` sueltos resuelven al stub roto de Windows -- siempre `./venv/Scripts/python.exe`.

## Review Focus

- Un residente que ya tiene cuenta (migración ya corrida) entra a "Mi perfil" -- el campo teléfono tiene que aparecer vacío, no tirar error por `Membresia.telefono` no seteado.
- Alguien se autoregistra SIN escribir teléfono (campo opcional) -- la cuenta se crea igual, `Membresia.telefono` queda `""`, no `None` ni error.
- El teléfono que ya tiene cargado un residente aparece precargado al abrir "Mi perfil" para editar (no empieza vacío cada vez).
- El `MembresiaSerializer` (el que ya usa el login de la API y `/auth/me/`) expone el teléfono actual -- si no se actualiza, la futura app no tiene cómo leerlo tras loguearse.
- Un residente con rol `delegado` o `conserjeria` puede cargar teléfono igual que uno `residente` -- el campo no está condicionado por rol en ningún lado del diseño.

---

## File Structure

```
core/
  models.py              (agregar campo Membresia.telefono)
  migrations/00XX_...py  (nueva, autogenerada)
  forms.py                (MiPerfilForm, RegistroResidenteForm -- agregar campo)
  serializers.py          (MiPerfilSerializer, MembresiaSerializer -- agregar campo)
  views.py                (MiPerfilView.form_valid o save ya cubre el form;
                            RegistroResidenteView.form_valid -- pasar telefono)
  api_views.py             (MeView.patch ya delega al serializer;
                            RegistroPublicoView.post -- pasar telefono)
  tests.py                 (tests nuevos)
```

---

### Task 1: Modelo -- `Membresia.telefono`

**Files:**
- Modify: `core/models.py` (clase `Membresia`)
- Create: `core/migrations/00XX_membresia_telefono.py` (autogenerada con `makemigrations`)
- Test: `core/tests.py`

**Interfaces:**
- Produces: `Membresia.telefono` -- `CharField(max_length=30, blank=True, default="")`. Todas las tareas siguientes lo consumen.

- [ ] **Step 1: Escribir el test que falla**

```python
# core/tests.py -- agregar a ModelosStrYPropiedadesTests o una clase nueva chica
class MembresiaTelefonoTests(TestCase):
    def test_telefono_es_opcional_y_vacio_por_defecto(self):
        condominio = Condominio.objects.create(nombre="Test Telefono Default", plan="premium")
        membresia = crear_membresia(condominio, "residente", unidad=Unidad.objects.create(condominio=condominio, numero="1"))
        self.assertEqual(membresia.telefono, "")
```

- [ ] **Step 2: Correr el test, confirmar que falla**

Run: `./venv/Scripts/python.exe manage.py test core.tests.MembresiaTelefonoTests --keepdb -v 2`
Expected: FAIL (`AttributeError: 'Membresia' object has no attribute 'telefono'`)

- [ ] **Step 3: Agregar el campo y migrar**

En `core/models.py`, dentro de `class Membresia`, junto a los demás campos:
```python
telefono = models.CharField(max_length=30, blank=True, default="", help_text="Para contacto directo -- opcional.")
```
Run: `./venv/Scripts/python.exe manage.py makemigrations core`

- [ ] **Step 4: Correr el test, confirmar que pasa**

Run: `./venv/Scripts/python.exe manage.py test core.tests.MembresiaTelefonoTests --keepdb -v 2`
Expected: PASS

- [ ] **Step 5: Suite completa + commit**

Run: `./venv/Scripts/python.exe manage.py test --keepdb` (background)
Expected: todos los tests en verde

```bash
git add core/models.py core/migrations/ core/tests.py
git commit -m "feat: agregar telefono a Membresia"
```

---

### Task 2: Mi perfil (web) -- ver y editar teléfono

**Files:**
- Modify: `core/forms.py:410-433` (`MiPerfilForm`)
- Test: `core/tests.py`

**Interfaces:**
- Consumes: `Membresia.telefono` (Tarea 1).
- Produces: `MiPerfilForm` con un campo `telefono` adicional (no viene de `Meta.model=User`, se guarda a mano en `save()` contra `request.user.membresia`).

**No existe una clase de test dedicada a `MiPerfilView` hoy** -- sus únicos
tests viven mezclados dentro de `EmailUnicoTests` (`core/tests.py:803`).
Crear una clase nueva, chica, propia:

- [ ] **Step 1: Escribir los tests que fallan**

```python
# core/tests.py -- clase nueva
class MiPerfilTelefonoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Mi Perfil Telefono", plan="premium")
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, numero="1")

    def setUp(self):
        self.membresia = crear_membresia(self.condominio, "residente", unidad=self.unidad, username="mi_perfil_tel", email="tel@example.com")
        self.client.force_login(self.membresia.user)

    def test_get_precarga_el_telefono_actual(self):
        self.membresia.telefono = "+56911112222"
        self.membresia.save(update_fields=["telefono"])
        r = self.client.get(reverse("mi-perfil"))
        self.assertContains(r, "+56911112222")

    def test_post_actualiza_el_telefono(self):
        r = self.client.post(reverse("mi-perfil"), {
            "first_name": "Mi", "last_name": "Perfil", "email": "tel@example.com", "telefono": "+56933334444",
        })
        self.assertRedirects(r, reverse("mi-perfil"))
        self.membresia.refresh_from_db()
        self.assertEqual(self.membresia.telefono, "+56933334444")

    def test_post_sin_telefono_lo_deja_vacio_no_falla(self):
        r = self.client.post(reverse("mi-perfil"), {
            "first_name": "Mi", "last_name": "Perfil", "email": "tel@example.com", "telefono": "",
        })
        self.assertRedirects(r, reverse("mi-perfil"))
        self.membresia.refresh_from_db()
        self.assertEqual(self.membresia.telefono, "")
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `./venv/Scripts/python.exe manage.py test core.tests -k Telefono --keepdb -v 2` (o el nombre exacto de la clase)
Expected: FAIL (el campo `telefono` no existe en el form -- `get_get_precarga` no encuentra el texto, el POST da error de campo inesperado o lo ignora sin guardar)

- [ ] **Step 3: Implementar**

En `MiPerfilForm` (`core/forms.py`):
```python
class MiPerfilForm(forms.ModelForm):
    telefono = forms.CharField(
        required=False, max_length=30, label="Teléfono",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "+56 9 ..."}),
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        # widgets/labels igual que hoy

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        membresia = getattr(self.instance, "membresia", None)
        if membresia is not None:
            self.fields["telefono"].initial = membresia.telefono

    # clean_first_name/clean_last_name/clean_email igual que hoy

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            membresia = getattr(user, "membresia", None)
            if membresia is not None:
                membresia.telefono = self.cleaned_data["telefono"]
                membresia.save(update_fields=["telefono"])
        return user
```
`MiPerfilView` (`core/views.py`) no cambia -- ya es un `UpdateView` que llama `form.save()` solo.

- [ ] **Step 4: Correr, confirmar que pasan**

Run: `./venv/Scripts/python.exe manage.py test core.tests -k Telefono --keepdb -v 2`
Expected: PASS

- [ ] **Step 5: Suite completa + commit**

```bash
git add core/forms.py core/tests.py
git commit -m "feat: editar telefono desde Mi perfil (web)"
```

---

### Task 3: Mi perfil (API) -- ver y editar teléfono

**Files:**
- Modify: `core/serializers.py:142-156` (`MiPerfilSerializer`), `core/serializers.py` (`MembresiaSerializer`, agregar campo)
- Test: `core/tests.py`

**Interfaces:**
- Consumes: `Membresia.telefono` (Tarea 1). Mismo patrón de "campo extra + save a mano" de la Tarea 2, del lado DRF.
- Produces: `GET/PATCH /api/v1/auth/me/` incluye `telefono`; el login (`POST /api/v1/auth/login/`) y `GET /api/v1/auth/me/` devuelven `telefono` dentro del objeto `membresia` embebido (`MembresiaSerializer`).

Estos 3 tests van dentro de la clase **ya existente**
`ApiMiPerfilYCambiarContrasenaTests` (`core/tests.py:999`), que ya tiene
`self.user`/`self.condominio` creados en `setUp` con password conocida
(`"clave-segura-123"`) y un helper `self._auth()` para el header Bearer:

- [ ] **Step 1: Escribir los tests que fallan**

```python
# core/tests.py -- agregar a ApiMiPerfilYCambiarContrasenaTests
def test_get_me_incluye_el_telefono_de_la_membresia(self):
    self.user.membresia.telefono = "+56911112222"
    self.user.membresia.save(update_fields=["telefono"])
    r = self.client.get(reverse("api-me"), **self._auth())
    self.assertEqual(r.json()["telefono"], "+56911112222")

def test_patch_me_actualiza_el_telefono(self):
    r = self.client.patch(reverse("api-me"), {"telefono": "+56933334444"}, content_type="application/json", **self._auth())
    self.assertEqual(r.status_code, 200)
    self.user.membresia.refresh_from_db()
    self.assertEqual(self.user.membresia.telefono, "+56933334444")

def test_login_devuelve_el_telefono_en_membresia(self):
    self.user.membresia.telefono = "+56911112222"
    self.user.membresia.save(update_fields=["telefono"])
    r = self.client.post(reverse("api-login"), {"username": "api_perfil_user", "password": "clave-segura-123"}, content_type="application/json")
    self.assertEqual(r.json()["membresia"]["telefono"], "+56911112222")
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `./venv/Scripts/python.exe manage.py test core.tests -k Telefono --keepdb -v 2`
Expected: FAIL (`KeyError`/`AssertionError`: `telefono` no está en la respuesta; PATCH no cambia nada)

- [ ] **Step 3: Implementar**

`MembresiaSerializer` (`core/serializers.py`): agregar `"telefono"` a `Meta.fields` (ya es un `ModelSerializer` sobre `Membresia`, el campo sale solo con `Meta.fields` -- no necesita declaración manual como en el form).

`MiPerfilSerializer`: mismo patrón que `MiPerfilForm` de la Tarea 2 -- agregar un `telefono = serializers.CharField(required=False, allow_blank=True)` fuera de `Meta.fields` (que sigue listando solo los de `User`), inicializarlo leyendo `self.instance.membresia.telefono` si hay instancia, y sobreescribir `save()` (o `update()`, que es lo que DRF llama acá) para guardar `Membresia.telefono` además de los campos de `User`.
`MeView.patch` (`core/api_views.py`) no cambia -- ya delega todo al serializer.

- [ ] **Step 4: Correr, confirmar que pasan**

Run: `./venv/Scripts/python.exe manage.py test core.tests -k Telefono --keepdb -v 2`
Expected: PASS

- [ ] **Step 5: Suite completa + commit**

```bash
git add core/serializers.py core/tests.py
git commit -m "feat: telefono en la API (Mi perfil, login, auth/me)"
```

---

### Task 4: Capturar el teléfono en el autoregistro (web y API)

**Files:**
- Modify: `core/forms.py:174-` (`RegistroResidenteForm`), `core/views.py` (`RegistroResidenteView.form_valid`), `core/api_views.py` (`RegistroPublicoView.post`)
- Test: `core/tests.py`

**Interfaces:**
- Consumes: `Membresia.telefono` (Tarea 1). `RegistroPublicoView.post` ya reusa `RegistroResidenteForm` tal cual (Fase 1) -- agregar el campo al Form alcanza para que la API lo reciba también, solo falta pasarlo al `Membresia.objects.create(...)` en los DOS lugares (vista web y vista API, cada una tiene su propio `Membresia.objects.create`).

- [ ] **Step 1: Escribir los tests que fallan**

```python
# core/tests.py -- agregar a CorreoBienvenidaTests (web, core/tests.py:730) y RegistroPublicoApiTests (API, core/tests.py:2601), clases ya existentes
# -- web:
def test_guarda_el_telefono_si_lo_escriben(self):
    r = self.client.post(reverse("registro-residente", kwargs={"token": self.condominio.token_registro_residentes}), {
        "nombre": "Nora", "apellido": "Lagos", "email": "nora@example.com", "unidad": self.unidad.pk,
        "telefono": "+56911112222",
        "password1": "unaClaveSegura123", "password2": "unaClaveSegura123", "acepto_terminos": True,
    })
    self.assertEqual(r.status_code, 302)
    membresia = Membresia.objects.get(user__email="nora@example.com")
    self.assertEqual(membresia.telefono, "+56911112222")

# -- API (en RegistroPublicoApiTests):
def test_post_guarda_el_telefono_si_lo_mandan(self):
    r = self.client.post(
        reverse("api-registro", args=[self.condominio.token_registro_residentes]),
        {
            "nombre": "Pedro", "apellido": "Pérez", "email": "pedro.telefono.api@example.com",
            "telefono": "+56911112222", "unidad": self.unidad.pk,
            "password1": "ClaveSegura123", "password2": "ClaveSegura123", "acepto_terminos": True,
        },
        content_type="application/json",
    )
    self.assertEqual(r.status_code, 201)
    membresia = Membresia.objects.get(user__username=r.json()["username"])
    self.assertEqual(membresia.telefono, "+56911112222")
```

(Para el test web: leer primero el `setUp`/los tests existentes de `RegistroResidenteViewTests` para copiar exactamente cómo arman el POST válido hoy -- el form tiene varios campos condicionales según modo casas/torre, ver `RegistroResidenteForm.__init__`.)

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `./venv/Scripts/python.exe manage.py test core.tests -k Telefono --keepdb -v 2`
Expected: FAIL (`Membresia.telefono` queda `""` aunque se mandó un valor)

- [ ] **Step 3: Implementar**

En `RegistroResidenteForm` (`core/forms.py`), agregar como campo normal del form (no como `MiPerfilForm`, acá no hay `Meta.model` -- es un `forms.Form` vía los mixins):
```python
telefono = forms.CharField(
    required=False, max_length=30, label="Tu teléfono (opcional)",
    widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "+56 9 ..."}),
)
```
Agregarlo también a `field_order` (línea ~177), después de `email`.

En `RegistroResidenteView.form_valid` (`core/views.py`) y en `RegistroPublicoView.post` (`core/api_views.py`), el `Membresia.objects.create(...)` de cada uno agrega `telefono=datos.get("telefono", "")`.

- [ ] **Step 4: Correr, confirmar que pasan**

Run: `./venv/Scripts/python.exe manage.py test core.tests -k Telefono --keepdb -v 2`
Expected: PASS

- [ ] **Step 5: Suite completa + commit**

```bash
git add core/forms.py core/views.py core/api_views.py core/tests.py
git commit -m "feat: capturar telefono opcional en el autoregistro (web y API)"
```

---

## Self-Review (hecho al escribir este plan)

**Cobertura del spec:** el único requisito es "agregar telefono al perfil del residente, en modelo, formulario/serializer de Mi perfil y de autoregistro, en API y en la pantalla de perfil de la app" -- Tarea 1 (modelo), Tarea 2 (Mi perfil web), Tarea 3 (Mi perfil API + login), Tarea 4 (autoregistro web+API). La "pantalla de perfil de la app" en sí es trabajo de la Fase 2 (app Expo), no de este plan -- este plan deja la API lista para que esa pantalla la consuma (Tarea 3).

**Review Focus:** los 5 puntos del header tienen test propio -- perfil vacío sin romper (Tarea 1 + Tarea 2/3), registro sin teléfono no falla (Tarea 4), precarga del valor existente (Tarea 2), login/me expone el campo (Tarea 3), ningún rol queda afuera (ningún task condiciona por rol, confirmado al no tocar ninguna lógica de permisos).

**Proporción:** 4 tareas chicas, todas tocan `core/` nada más, sin nuevas dependencias ni archivos nuevos salvo la migración autogenerada.

## Qué queda a criterio de quien lo construya

- Formato/validación exacta del teléfono (si se exige un patrón tipo `+56 9 XXXX XXXX` o se acepta cualquier texto) -- el diseño no lo pidió, se deja como texto libre igual que `SolicitudAcceso.telefono` ya hace hoy.

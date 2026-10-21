# "Visto por" en una alerta Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el autor de una alerta pueda ver cuántos vecinos de su propio condominio ya la vieron, y que marcarla como vista sea una acción explícita del vecino (nunca pasiva).

**Architecture:** Mismo patrón que `AvisoLectura`/`marcar_leido` (`comunicacion/`), adaptado a Alerta: un modelo `AlertaLectura` nuevo, una acción `marcar_visto` en `AlertaViewSet`, y un campo `visto_por_count` en `AlertaSerializer` -- visible solo para el propio autor (no por rol/staff, a diferencia de Avisos), y contando solo miembros del condominio dueño de la alerta (no la red de condominios vecinos).

**Tech Stack:** Django 6.1.2, DRF -- mismo stack, sin dependencias nuevas.

**Spec:** `docs/superpowers/specs/2026-10-19-app-movil-mi-barrio-design.md` (D-05: "visto por" en una alerta -- qué cuenta como visto, a quién se cuenta, quién lo ve).

## Global Constraints

- Marcar "visto" es una acción explícita del cliente (`POST`), nunca automática al listar/sincronizar -- mismo criterio que `AvisoViewSet.marcar_leido` ya aplica, decidido explícitamente para Alertas en D-05 del spec (un conteo que se marca solo por sincronización pasiva "miente" en el peor momento).
- `visto_por_count` solo es visible para el propio autor de la alerta (`request.user == alerta.autor.user`) -- cualquier otro (otro vecino, devquad, un miembro de un condominio vecino de la red) recibe `null` en ese campo, nunca un número.
- El conteo nunca incluye a miembros de condominios vecinos (`ids_red_alertas`), aunque también reciban la alerta -- solo miembros del condominio dueño.
- TDD: cada cambio entra con su test en rojo primero. Suite completa (`./venv/Scripts/python.exe manage.py test --keepdb`, en background) en verde antes de cada commit.
- `python`/`pip` sueltos resuelven al stub roto de Windows -- siempre `./venv/Scripts/python.exe`.

## Review Focus

- Alguien de un condominio VECINO (de la red de alertas) llama a `marcar_visto` -- no debe contar para `visto_por_count` del condominio dueño, aunque la alerta le aparezca en su propia lista.
- Devquad (sin `Membresia`) llama a `marcar_visto` -- no debe romper (mismo caso ya resuelto para `AvisoViewSet.marcar_leido`, "no hay leído por que registrarle").
- Un vecino que NO es el autor pide el detalle de la alerta -- `visto_por_count` tiene que ser `null`, no `0` (que insinuaría "nadie la ha visto" en vez de "no te corresponde saberlo").
- Marcar visto dos veces la misma persona -- el conteo no debe duplicar (constraint de unicidad, igual que `AvisoLectura`).
- El propio autor marca su propia alerta como vista -- ¿se cuenta a sí mismo? (Resuelto en D-01 de este plan: sí, nada en el spec lo excluye, y simplifica el código no tener un caso especial.)

---

## File Structure

```
alertas/
  models.py               (agregar AlertaLectura)
  migrations/00XX_...py   (nueva, autogenerada)
  serializers.py           (AlertaSerializer -- agregar visto_por_count)
  api_views.py             (AlertaViewSet -- agregar accion marcar_visto)
  tests.py                 (tests nuevos)
```

---

### Task 1: Modelo `AlertaLectura`

**Files:**
- Modify: `alertas/models.py`
- Create: `alertas/migrations/00XX_alertalectura.py` (autogenerada)
- Test: `alertas/tests.py`

**Interfaces:**
- Produces: `AlertaLectura(alerta: FK[Alerta], membresia: FK[Membresia], fecha_lectura: DateTimeField(auto_now_add))`, con `UniqueConstraint(alerta, membresia)`. Todas las tareas siguientes lo consumen.

- [ ] **Step 1: Escribir el test que falla**

```python
# alertas/tests.py
class AlertaLecturaModeloTests(TestCase):
    def test_no_se_puede_registrar_dos_veces_la_misma_lectura(self):
        condominio = Condominio.objects.create(nombre="Test Alerta Lectura Modelo", plan="premium")
        autor = crear_membresia(condominio, "residente", username="lectura_modelo_autor")
        alerta = Alerta.objects.create(condominio=condominio, autor=autor, tipo="robo", estado="activa")
        from alertas.models import AlertaLectura
        AlertaLectura.objects.create(alerta=alerta, membresia=autor)
        with self.assertRaises(IntegrityError):
            AlertaLectura.objects.create(alerta=alerta, membresia=autor)
```

(`from django.db import IntegrityError` ya hace falta importarlo si no está arriba del archivo.)

- [ ] **Step 2: Correr el test, confirmar que falla**

Run: `./venv/Scripts/python.exe manage.py test alertas.tests.AlertaLecturaModeloTests --keepdb -v 2`
Expected: FAIL (`ImportError: cannot import name 'AlertaLectura'`)

- [ ] **Step 3: Implementar**

En `alertas/models.py`, al final del archivo (mismo estilo que `AvisoLectura` en `comunicacion/models.py:27-42`):
```python
class AlertaLectura(models.Model):
    """Quién vio cada alerta -- base de "visto por X vecinos", visible
    solo para el propio autor (ver AlertaSerializer.get_visto_por_count).
    Se registra con una acción explícita (marcar_visto), nunca pasiva."""

    alerta = models.ForeignKey(Alerta, on_delete=models.CASCADE, related_name="lecturas")
    membresia = models.ForeignKey(Membresia, on_delete=models.CASCADE, related_name="alertas_vistas")
    fecha_lectura = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["alerta", "membresia"], name="lectura_unica_por_alerta_y_membresia"),
        ]

    def __str__(self):
        return f"{self.membresia} vio la alerta #{self.alerta_id}"
```
(Importar `Membresia` desde `core.models` si `alertas/models.py` no la tiene ya importada -- revisar el import existente de `Condominio`/`Membresia` arriba del archivo.)

Run: `./venv/Scripts/python.exe manage.py makemigrations alertas`

- [ ] **Step 4: Correr el test, confirmar que pasa**

Run: `./venv/Scripts/python.exe manage.py test alertas.tests.AlertaLecturaModeloTests --keepdb -v 2`
Expected: PASS

- [ ] **Step 5: Suite completa + commit**

```bash
git add alertas/models.py alertas/migrations/ alertas/tests.py
git commit -m "feat: modelo AlertaLectura (quien vio una alerta)"
```

---

### Task 2: Acción `marcar_visto`

**Files:**
- Modify: `alertas/api_views.py` (`AlertaViewSet`)
- Test: `alertas/tests.py`

**Interfaces:**
- Consumes: `AlertaLectura` (Tarea 1).
- Produces: `POST /api/v1/alertas/<id>/marcar_visto/` -- crea (o ignora si ya existe) un `AlertaLectura` para `request.user.membresia` y esa alerta, SOLO si esa membresía pertenece al condominio dueño de la alerta (no a un condominio vecino de la red). Devuelve `200` con el `AlertaSerializer` de la alerta (sin exponer el conteo salvo que quien llama sea el autor -- eso ya lo resuelve el serializer de la Tarea 3).

- [ ] **Step 1: Escribir los tests que fallan**

```python
# alertas/tests.py
class MarcarVistoAlertaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Marcar Visto", plan="premium")

    def setUp(self):
        self.autor = crear_membresia(self.condominio, "residente", username="marcar_visto_autor")
        self.vecino = crear_membresia(self.condominio, "residente", username="marcar_visto_vecino")
        self.alerta = Alerta.objects.create(condominio=self.condominio, autor=self.autor, tipo="robo", estado="activa")

    def test_un_vecino_puede_marcarla_como_vista(self):
        from alertas.models import AlertaLectura
        self.client.force_login(self.vecino.user)
        r = self.client.post(reverse("alerta-marcar-visto", kwargs={"pk": self.alerta.pk}))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(AlertaLectura.objects.filter(alerta=self.alerta, membresia=self.vecino).exists())

    def test_marcarla_dos_veces_no_duplica(self):
        from alertas.models import AlertaLectura
        self.client.force_login(self.vecino.user)
        self.client.post(reverse("alerta-marcar-visto", kwargs={"pk": self.alerta.pk}))
        self.client.post(reverse("alerta-marcar-visto", kwargs={"pk": self.alerta.pk}))
        self.assertEqual(AlertaLectura.objects.filter(alerta=self.alerta, membresia=self.vecino).count(), 1)

    def test_devquad_no_rompe_aunque_no_tenga_membresia(self):
        self.client.force_login(crear_devquad("marcar_visto_devquad"))
        self.client.get(reverse("devquad-entrar-condominio", args=[self.condominio.pk]))
        r = self.client.post(reverse("alerta-marcar-visto", kwargs={"pk": self.alerta.pk}))
        self.assertEqual(r.status_code, 200)

    def test_un_miembro_de_un_condominio_vecino_no_cuenta(self):
        from alertas.models import AlertaLectura
        vecino_otro_condominio = Condominio.objects.create(nombre="Test Marcar Visto Vecino Red", plan="premium")
        self.condominio.condominios_vecinos.add(vecino_otro_condominio)
        residente_vecino = crear_membresia(vecino_otro_condominio, "residente", username="marcar_visto_red")
        self.client.force_login(residente_vecino.user)
        r = self.client.post(reverse("alerta-marcar-visto", kwargs={"pk": self.alerta.pk}))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(AlertaLectura.objects.filter(alerta=self.alerta, membresia=residente_vecino).exists())
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `./venv/Scripts/python.exe manage.py test alertas.tests.MarcarVistoAlertaTests --keepdb -v 2`
Expected: FAIL (`NoReverseMatch` -- la acción todavía no existe)

- [ ] **Step 3: Implementar**

En `AlertaViewSet` (`alertas/api_views.py`), mismo estilo que `AvisoViewSet.marcar_leido` (`comunicacion/api_views.py:50-59`):
```python
@action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, TieneCondominioActivo])
def marcar_visto(self, request, pk=None):
    alerta = self.get_object()
    membresia = getattr(request.user, "membresia", None)
    if membresia is not None and membresia.condominio_id == alerta.condominio_id:
        AlertaLectura.objects.get_or_create(alerta=alerta, membresia=membresia)
    return Response(AlertaSerializer(alerta, context={"request": request}).data)
```
(`AlertaViewSet` ya importa `action`/`IsAuthenticated` -- solo falta agregar `AlertaLectura` al `from .models import Alerta` existente.)

- [ ] **Step 4: Correr, confirmar que pasan**

Run: `./venv/Scripts/python.exe manage.py test alertas.tests.MarcarVistoAlertaTests --keepdb -v 2`
Expected: PASS

- [ ] **Step 5: Suite completa + commit**

```bash
git add alertas/api_views.py alertas/tests.py
git commit -m "feat: accion marcar_visto en AlertaViewSet"
```

---

### Task 3: `visto_por_count` en `AlertaSerializer` -- solo para el autor

**Files:**
- Modify: `alertas/serializers.py` (`AlertaSerializer`)
- Test: `alertas/tests.py`

**Interfaces:**
- Consumes: `AlertaLectura` (Tarea 1).
- Produces: `AlertaSerializer` con un campo nuevo `visto_por_count: int | null` -- `null` para cualquiera que no sea el autor de la alerta, un entero (conteo de `alerta.lecturas.count()`) para el autor.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# alertas/tests.py
class VistoPorCountSerializerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre="Test Visto Por Count", plan="premium")

    def setUp(self):
        self.autor = crear_membresia(self.condominio, "residente", username="visto_count_autor")
        self.vecino = crear_membresia(self.condominio, "residente", username="visto_count_vecino")
        self.alerta = Alerta.objects.create(condominio=self.condominio, autor=self.autor, tipo="robo", estado="activa")
        from alertas.models import AlertaLectura
        AlertaLectura.objects.create(alerta=self.alerta, membresia=self.vecino)

    def test_el_autor_ve_el_conteo(self):
        self.client.force_login(self.autor.user)
        r = self.client.get(reverse("alerta-detail", kwargs={"pk": self.alerta.pk}))
        self.assertEqual(r.json()["visto_por_count"], 1)

    def test_otro_vecino_no_ve_el_conteo(self):
        self.client.force_login(self.vecino.user)
        r = self.client.get(reverse("alerta-detail", kwargs={"pk": self.alerta.pk}))
        self.assertIsNone(r.json()["visto_por_count"])
```

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `./venv/Scripts/python.exe manage.py test alertas.tests.VistoPorCountSerializerTests --keepdb -v 2`
Expected: FAIL (`KeyError: 'visto_por_count'`)

- [ ] **Step 3: Implementar**

En `AlertaSerializer` (`alertas/serializers.py`), agregar:
```python
visto_por_count = serializers.SerializerMethodField()

def get_visto_por_count(self, obj) -> Optional[int]:
    request = self.context.get("request")
    if not (request and request.user.id == obj.autor.user_id):
        return None
    return obj.lecturas.count()
```
Agregar `"visto_por_count"` a `Meta.fields`, y `from typing import Optional` arriba del archivo si no está ya (mismo estilo que `comunicacion/serializers.py: get_leido_por_count`).

- [ ] **Step 4: Correr, confirmar que pasan**

Run: `./venv/Scripts/python.exe manage.py test alertas.tests.VistoPorCountSerializerTests --keepdb -v 2`
Expected: PASS

- [ ] **Step 5: Suite completa + commit**

```bash
git add alertas/serializers.py alertas/tests.py
git commit -m "feat: visto_por_count en AlertaSerializer, visible solo para el autor"
```

---

## Self-Review (hecho al escribir este plan)

**Cobertura del spec:** D-05 completo -- qué cuenta como visto (Tarea 2, acción explícita), a quién se cuenta (Tarea 2, filtro por condominio dueño), quién lo ve (Tarea 3, solo el autor).

**Review Focus:** los 5 puntos tienen test propio -- condominio vecino no cuenta (Tarea 2), devquad no rompe (Tarea 2), no-autor ve `null` no `0` (Tarea 3), duplicado no se cuenta dos veces (Tarea 2), autor contándose a sí mismo (decisión explícita en el header, sin caso especial en el código -- si el autor llama a `marcar_visto` sobre su propia alerta, igual que cualquier otro miembro de su condominio, queda registrado).

**Proporción:** 3 tareas chicas, todas en `alertas/`, mismo tamaño que el patrón ya probado de `AvisoLectura`.

## Qué queda a criterio de quien lo construya

- Si la futura app móvil llama a `marcar_visto` automáticamente al abrir el detalle de una alerta, o requiere un botón -- es una decisión de UI de la Fase 2 (app), no de este plan de backend.

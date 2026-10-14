---
name: securapp-conventions
description: Convenciones de ingeniería específicas del proyecto SecurApp Copropiedad (Django multi-tenant para condominios/juntas de vecinos en Chile). Consulta esta skill SIEMPRE que trabajes dentro del repo SecurApp_Copropiedad -- al tocar permisos/mixins, agregar un rol o un ViewSet de DRF, correr tests, hacer una migración, o validar el Quality Gate de SonarCloud. También úsala si algo no cuadra con lo que ves en el código: puede ser una regresión conocida de Django 6.1, no un bug nuevo.
---

# SecurApp Copropiedad -- convenciones del proyecto

Django 6.1 + DRF, multi-tenant (cada fila pertenece a un `Condominio`), corriendo en Windows durante desarrollo y Render en producción. Lo de abajo es todo cosas que costó descubrir a mano -- la idea es no volver a pisar el mismo rastrillo.

## Cómo correr cosas en esta máquina

`python` y `pip` sueltos en el PATH resuelven al stub roto de Microsoft Store (imprime un mensaje de error en español y no corre nada). Usa siempre el intérprete del venv del proyecto:

```
./venv/Scripts/python.exe manage.py test
./venv/Scripts/python.exe manage.py check
./venv/Scripts/python.exe manage.py makemigrations
```

El suite completo (~450-470 tests) tarda 90-140 segundos -- córrelo en background y sigue trabajando mientras termina, en vez de esperar bloqueado.

## Permisos, mixins y aislamiento multi-tenant

- **Orden de mixins**: los mixins de restricción de rol (`SoloDirectivaMixin`, `EsDirectivaOAdministracionMixin`, `EsDirectivaAdministracionOConserjeMixin`, `SoloAdministracionMixin`, `SoloStaffMixin`) van **antes** de `CondominioRequiredMixin`/`CondominioFormMixin` en el MRO -- así el rechazo por rol pasa antes de que el mixin de condominio intente resolver `self.membresia`.
- **DRF**: `CondominioQuerysetMixin` (core/permissions.py) filtra automáticamente el queryset de cualquier ViewSet por `request.user.membresia.condominio_id`. Mézclalo siempre que un ViewSet exponga datos de un modelo con FK a `Condominio`.
- **Bug recurrente a evitar**: si un ViewSet sobreescribe `get_permissions()`, compara contra `self.action` (`"create"`, `"destroy"`, el nombre de un `@action` custom), **nunca** contra `self.request.method`. Comparar por método HTTP aplica el permiso equivocado a cualquier `@action` nueva que comparta ese verbo -- pasó de verdad con `AvisoViewSet.marcar_leido` (POST) heredando el permiso pensado para `create` (también POST).
- **Nunca confíes en una FK sensible que venga del cliente.** Para cualquier dato que cruce de "todo el condominio" a "solo mi torre/unidad" (scoping de Avisos, Publicaciones, notificaciones push), el cliente manda como máximo un booleano (`solo_mi_torre`); la vista resuelve la FK real server-side a partir de `request.user.membresia.unidad.torre`. Nunca aceptes un `torre_id` crudo del body -- permitiría escribir contenido "acotado" a una torre ajena.

## Migraciones

Esta app ya está desplegada en producción (Render). **Nunca edites ni borres una migración ya commiteada** -- aunque parezca más prolijo squashearla, ya corrió contra la base de datos real. Para deshacer algo (ej. borrar un modelo que ya no se usa), siempre agrega una migración NUEVA (`migrations.DeleteModel`, `migrations.RemoveField`, etc.) que dependa de la última.

## Regresión conocida: Django 6.1 y `ModelChoiceField`

El `empty_label` por defecto de `ModelChoiceField` en esta instalación es el string en inglés sin traducir `"- Select an option -"` (no el `"---------"` de siempre), porque el catálogo `es-cl` instalado no lo tiene cubierto. Si ves ese texto en inglés en un `<select>`, no es un bug nuevo: pon `empty_label="---------"` (o un texto en español) explícito en el field. Esto afecta a cualquier `ModelChoiceField` del proyecto, y por separado también a los formfields que autogenera el admin de `django-unfold` para FKs normales (no las que usan `autocomplete_fields`).

## Agregar un rol nuevo

`ROL_CHOICES` vive en `core/models.py`. Al agregar un rol, revisa (no asumas que "funciona solo"):
1. `Membresia.clean()` -- si el rol necesita `unidad` obligatoria.
2. `CrearMiembroForm` en `core/forms.py` -- quién puede asignarlo (`creador_rol`).
3. Cualquier vista/queryset que filtre por rol con una lista cerrada tipo `if rol == "residente": ... else: ...` (patrón de exclusión) en vez de `if rol in (lista de roles con privilegio): ...` (patrón de lista blanca) -- el primero le da acceso de más al rol nuevo sin querer. Pasó de verdad en `CuotaUnidadViewSet.get_queryset`.
4. Templates que gatean UI por `membresia.rol == "x"` (nav, inicio.html) -- un rol nuevo no aparece en ningún lado hasta que se agrega explícito.

## SonarCloud

Es un proyecto público, no hace falta token para consultar el Quality Gate:
```
curl -s "https://sonarcloud.io/api/qualitygates/project_status?projectKey=LSJ-tech_Condofy"
curl -s "https://sonarcloud.io/api/project_analyses/search?project=LSJ-tech_Condofy&ps=5"
```
El segundo endpoint trae el `revision` (hash de commit) de cada análisis -- confirma que el análisis más reciente corresponde al commit que esperas antes de reportar el resultado, el CI tarda unos minutos en correr después del push.

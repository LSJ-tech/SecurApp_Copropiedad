import datetime

from django.contrib import admin
from django.db.models.functions import Length
from django.utils import timezone
from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.filters.admin import AutocompleteSelectFilter

from .models import PLAN_CHOICES, CodigoInvitacion, Condominio, Membresia, SolicitudAcceso, SolicitudEliminacion, Torre, Unidad

# Unidad/Torre/Membresia son datos operativos de cada condominio -- se
# registran acá porque, a diferencia de PataAgenda, no hay un panel interno
# rico todavía para gestionarlos (Fase 1 usa el panel simple bajo /panel/).


@admin.action(description="Extender 30 días de acceso pagado")
def extender_30_dias(modeladmin, request, queryset):
    hoy = timezone.localdate()
    for condominio in queryset:
        base = condominio.pagado_hasta if condominio.pagado_hasta and condominio.pagado_hasta > hoy else hoy
        condominio.pagado_hasta = base + datetime.timedelta(days=30)
        condominio.save()


def _cambiar_plan(plan):
    @admin.action(description=f"Cambiar a plan {dict(PLAN_CHOICES)[plan]}")
    def accion(modeladmin, request, queryset):
        queryset.update(plan=plan)
    accion.__name__ = f"cambiar_a_{plan}"
    return accion


cambiar_a_free = _cambiar_plan("free")
cambiar_a_premium = _cambiar_plan("premium")


# Tope de filas que se muestran inline en el admin de Condominio. Un condominio
# real (ej. Empart: ~300 unidades) vuelve la página lentísima si se listan
# TODAS sus unidades/membresías ahí -- para eso ya existen las páginas propias
# de Unidad y Membresia (paginadas y filtrables por condominio).
MAX_FILAS_INLINE = 30


class UnidadInline(TabularInline):
    model = Unidad
    extra = 0
    fields = ["numero", "torre", "alicuota"]
    verbose_name_plural = f"Unidades (primeras {MAX_FILAS_INLINE} -- para ver/editar el resto, ir a Unidades y filtrar por este condominio)"

    def get_queryset(self, request):
        qs = super().get_queryset(request).annotate(
            _torre_len=Length("torre__nombre"), _num_len=Length("numero"),
        ).order_by("_torre_len", "torre__nombre", "_num_len", "numero")
        ids = list(qs.values_list("pk", flat=True)[:MAX_FILAS_INLINE])
        return qs.filter(pk__in=ids)


class MembresiaInline(TabularInline):
    model = Membresia
    extra = 0
    # autocomplete en "unidad" es obligatorio, no solo prolijo: sin esto Django
    # arma un <select> con TODAS las unidades del sistema por cada fila, y con
    # un condominio real (ej. Empart: 300 unidades x 300 membresías) la página
    # tarda minutos y pesa decenas de MB -- se cae con timeout en producción.
    autocomplete_fields = ["user", "unidad"]
    verbose_name = "Usuario vinculado"
    verbose_name_plural = (
        f"Usuarios vinculados (directiva / conserjería / residentes) -- primeros {MAX_FILAS_INLINE}, "
        "para ver/editar el resto ir a Membresías y filtrar por este condominio"
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request).order_by("rol", "user__username")
        ids = list(qs.values_list("pk", flat=True)[:MAX_FILAS_INLINE])
        return qs.filter(pk__in=ids)


@admin.register(Condominio)
class CondominioAdmin(ModelAdmin):
    list_display = ["nombre", "plan", "es_fundador", "estado_suscripcion", "activo", "fecha_creacion"]
    list_filter = ["plan", "es_fundador", "activo"]
    search_fields = ["nombre"]
    actions = [extender_30_dias, cambiar_a_free, cambiar_a_premium]
    inlines = [UnidadInline, MembresiaInline]
    filter_horizontal = ["condominios_vecinos"]

    @admin.display(description="Suscripción")
    def estado_suscripcion(self, obj):
        if obj.pagado_hasta is None:
            return "Sin restricción"
        return f"{'Vencida' if obj.esta_vencido else 'Vigente'} hasta {obj.pagado_hasta}"


@admin.register(Torre)
class TorreAdmin(ModelAdmin):
    """Orden numérico real (1, 2, 3... no "1, 10, 11...") -- mismo truco de
    Length() ya usado en TorreListView/UnidadListView del panel web, que acá
    nunca se había aplicado al propio admin."""

    list_display = ["nombre", "condominio"]
    list_filter = [("condominio", AutocompleteSelectFilter)]
    search_fields = ["nombre"]  # exigido por AutocompleteSelectFilter en otros admin que filtran por torre (ej. MembresiaAdmin)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_len=Length("nombre")).order_by("condominio__nombre", "_len", "nombre")


@admin.register(Unidad)
class UnidadAdmin(ModelAdmin):
    list_display = ["numero", "condominio", "torre", "alicuota"]
    list_filter = [("condominio", AutocompleteSelectFilter), ("torre", AutocompleteSelectFilter)]
    search_fields = ["numero", "torre__nombre", "condominio__nombre"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _torre_len=Length("torre__nombre"), _num_len=Length("numero"),
        ).order_by("condominio__nombre", "_torre_len", "torre__nombre", "_num_len", "numero")


@admin.register(Membresia)
class MembresiaAdmin(ModelAdmin):
    """Filtros como desplegable con buscador (AutocompleteSelectFilter) en vez
    de la lista larga de links que da el filtro por defecto -- con 27+
    condominios/cientos de unidades y subiendo, esa lista ya no es manejable.
    Orden de los filtros: de lo más amplio (condominio) a lo más puntual
    (block, depto), con el rol aparte al final por ser un atributo
    transversal, no parte de esa jerarquía."""

    list_display = ["user", "condominio", "rol", "unidad"]
    list_filter = [
        ("condominio", AutocompleteSelectFilter),
        ("unidad__torre", AutocompleteSelectFilter),
        ("unidad", AutocompleteSelectFilter),
        "rol",
    ]
    autocomplete_fields = ["user", "unidad"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _torre_len=Length("unidad__torre__nombre"), _num_len=Length("unidad__numero"),
        ).order_by("condominio__nombre", "_torre_len", "unidad__torre__nombre", "_num_len", "unidad__numero", "rol", "user__username")


@admin.register(CodigoInvitacion)
class CodigoInvitacionAdmin(ModelAdmin):
    """"Añadir" ya genera un código nuevo solo (ver default del campo) -- basta con Guardar."""

    list_display = ["codigo", "usado_display", "condominio", "fecha_creacion", "fecha_uso"]
    list_filter = ["fecha_creacion"]
    readonly_fields = ["condominio", "fecha_uso"]

    @admin.display(description="Usado", boolean=True)
    def usado_display(self, obj):
        return obj.usado


@admin.action(description="Marcar como atendido")
def marcar_atendido(modeladmin, request, queryset):
    queryset.update(atendido=True)


@admin.register(SolicitudAcceso)
class SolicitudAccesoAdmin(ModelAdmin):
    list_display = ["condominio", "nombre", "comuna", "telefono", "atendido", "fecha_creacion"]
    list_filter = ["atendido", "comuna"]
    search_fields = ["nombre", "condominio", "telefono", "email"]
    actions = [marcar_atendido]


@admin.action(description="Marcar como atendida")
def marcar_atendida(modeladmin, request, queryset):
    queryset.update(atendida=True, fecha_atencion=timezone.now())


@admin.register(SolicitudEliminacion)
class SolicitudEliminacionAdmin(ModelAdmin):
    list_display = ["nombre", "username", "condominio_nombre", "atendida", "fecha_creacion"]
    list_filter = ["atendida"]
    search_fields = ["nombre", "username", "condominio_nombre"]
    readonly_fields = ["membresia", "nombre", "username", "condominio_nombre", "motivo", "fecha_creacion"]
    actions = [marcar_atendida]

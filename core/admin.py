import datetime

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from django.db.models.functions import Length
from django.shortcuts import redirect
from django.utils import timezone
from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.filters.admin import AutocompleteSelectFilter
from unfold.decorators import action, display
from unfold.forms import AdminPasswordChangeForm, BaseDialogForm, UserChangeForm, UserCreationForm
from unfold.views import ChangeList

from .comunas_chile import COMUNAS_POR_REGION, comuna_choices_agrupadas
from .models import PLAN_CHOICES, REGION_CHOICES, Condominio, Membresia, SolicitudAcceso, SolicitudEliminacion, Torre, Unidad

# Unidad/Torre/Membresia son datos operativos de cada condominio -- se
# registran acá porque, a diferencia de PataAgenda, no hay un panel interno
# rico todavía para gestionarlos (Fase 1 usa el panel simple bajo /panel/).


class ChangeListOrdenAnotado(ChangeList):
    """El ChangeList de Django SIEMPRE vuelve a ordenar después de
    get_queryset() -- primero intenta ModelAdmin.get_ordering(request), y
    si no hay nada ahí cae al Meta.ordering del modelo (alfabético). Eso
    pisa cualquier .order_by() con campos anotados (Length(), ver
    TorreAdmin/UnidadAdmin/MembresiaAdmin) que get_queryset() ya haya
    dejado armado, y ni siquiera se puede resolver ModelAdmin.get_ordering()
    con esos mismos nombres: ese método también lo llama el get_queryset()
    base de Django ANTES de que exista la anotación, así que truena con
    FieldError. La salida es confiar directo en el order_by que el propio
    queryset ya trae (ChangeListOrdenAnotado.get_ordering), sin pasar por
    ninguno de esos dos mecanismos."""

    def get_ordering(self, request, queryset):
        return list(queryset.query.order_by) or ["-pk"]


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
    fields = ["numero", "calle", "torre", "alicuota"]
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


class EstadoSuscripcionFilter(admin.SimpleListFilter):
    """El cobro de la suscripción es manual (no hay corte automático, ver
    SuscripcionActivaMixin) -- este filtro es la lista de seguimiento de
    cobro: encontrar rápido a quién hay que escribirle. Mismas 3 categorías
    que ya calcula CondominioAdmin.estado_suscripcion, solo que ese método
    no se puede usar en list_filter porque no es un campo real del modelo."""

    title = "estado de suscripción"
    parameter_name = "estado_suscripcion"

    def lookups(self, request, model_admin):
        return [("vencida", "Vencida"), ("vigente", "Vigente"), ("libre", "Sin restricción")]

    def queryset(self, request, queryset):
        hoy = timezone.localdate()
        if self.value() == "vencida":
            return queryset.filter(pagado_hasta__lt=hoy)
        if self.value() == "vigente":
            return queryset.filter(pagado_hasta__gte=hoy)
        if self.value() == "libre":
            return queryset.filter(pagado_hasta__isnull=True)
        return queryset


class ComunaAdminWidget(forms.Select):
    """Carga el JS de la cascada región/comuna del admin (ver
    core/static/core/js/admin_condominio_cascada.js) -- declararlo en la
    Media del widget basta para que Django admin lo agregue solo, sin
    tocar ningún template."""

    class Media:
        js = [
            "core/js/cascada_region_comuna.js",
            "core/js/datos_comunas_chile.js",
            "core/js/admin_condominio_cascada.js",
        ]


class CondominioAdminForm(forms.ModelForm):
    """region/comuna como desplegable (antes texto libre) -- comuna en
    cascada según la región elegida, mismo dato que usa el formulario
    de alta de condominio de devquad (ver CrearCondominioForm)."""

    region = forms.ChoiceField(choices=[("", "---------")] + REGION_CHOICES, required=False, label="Región")
    comuna = forms.ChoiceField(
        choices=[("", "---------")] + comuna_choices_agrupadas(REGION_CHOICES), required=False, label="Comuna",
        widget=ComunaAdminWidget,
    )

    class Meta:
        model = Condominio
        # Explícitos en vez de "__all__" -- así un campo nuevo que se agregue
        # al modelo más adelante no aparece solo en el admin sin que alguien
        # decida a propósito mostrarlo acá.
        fields = [
            "nombre", "etiqueta_organizacion", "direccion", "comuna", "region", "activo", "plan",
            "pagado_hasta", "es_fundador", "datos_transferencia", "etiqueta_torre", "etiqueta_unidad", "genero_unidad",
        ]

    def clean(self):
        cleaned = super().clean()
        region = cleaned.get("region")
        comuna = cleaned.get("comuna")
        if region and comuna and comuna not in COMUNAS_POR_REGION.get(region, []):
            raise forms.ValidationError("Esa comuna no pertenece a la región elegida.")
        return cleaned


@admin.register(Condominio)
class CondominioAdmin(ModelAdmin):
    form = CondominioAdminForm
    list_display = ["nombre", "plan", "es_fundador", "estado_suscripcion", "activo", "fecha_creacion"]
    list_filter = ["plan", "es_fundador", "activo", EstadoSuscripcionFilter]
    search_fields = ["nombre"]
    actions = [extender_30_dias, cambiar_a_free, cambiar_a_premium]
    inlines = [UnidadInline, MembresiaInline]
    filter_horizontal = ["condominios_vecinos"]

    @display(description="Suscripción", label={"vigente": "success", "vencida": "danger", "libre": "info"})
    def estado_suscripcion(self, obj):
        if obj.pagado_hasta is None:
            return "libre", "Sin restricción"
        if obj.esta_vencido:
            return "vencida", f"Vencida hace {(timezone.localdate() - obj.pagado_hasta).days} días"
        return "vigente", f"Vigente hasta {obj.pagado_hasta:%d-%m-%Y}"


@admin.register(Torre)
class TorreAdmin(ModelAdmin):
    """Orden numérico real (1, 2, 3... no "1, 10, 11...") -- mismo truco de
    Length() ya usado en TorreListView/UnidadListView del panel web, que acá
    nunca se había aplicado al propio admin."""

    list_display = ["nombre", "condominio"]
    list_filter = [("condominio", AutocompleteSelectFilter)]
    list_filter_submit = True  # sin esto el desplegable no tiene botón "Aplicar filtros" y elegir una opción no hace nada
    search_fields = ["nombre"]  # exigido por AutocompleteSelectFilter en otros admin que filtran por torre (ej. MembresiaAdmin)
    list_select_related = ["condominio"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_len=Length("nombre")).order_by("condominio__nombre", "_len", "nombre")

    def get_changelist(self, request, **kwargs):
        return ChangeListOrdenAnotado


class CrearUnidadesEnLoteForm(BaseDialogForm):
    """Onboardear un condominio grande a mano, unidad por unidad, es lento
    y repetitivo (ej. las ~300 de Empart) -- este form genera un rango
    numerado de una vez. MAX_UNIDADES_POR_LOTE es solo un tope de cordura
    contra un rango tipeado mal (ej. 1 a 99999), no un límite de negocio."""

    MAX_UNIDADES_POR_LOTE = 500

    # empty_label explícito en español en los dos -- el default de Django
    # 6.1 ("- Select an option -") no está traducido en el catálogo "es-cl"
    # instalado.
    condominio = forms.ModelChoiceField(queryset=Condominio.objects.all(), label="Condominio", empty_label="Elige un condominio")
    torre = forms.ModelChoiceField(
        queryset=Torre.objects.all(), required=False, label="Torre (opcional)", empty_label="No aplica",
        help_text="Dejar vacío si son casas o unidades sin torre.",
    )
    calle = forms.CharField(
        required=False, label="Calle (opcional)",
        help_text="Si la junta de vecinos tiene varias calles, para no mezclar casas con el mismo número.",
    )
    prefijo = forms.CharField(required=False, label="Prefijo", help_text="Ej. \"A-\" para generar A-101, A-102...")
    desde = forms.IntegerField(label="Número inicial", min_value=1)
    hasta = forms.IntegerField(label="Número final", min_value=1)
    alicuota = forms.DecimalField(
        required=False, max_digits=6, decimal_places=4, label="Alícuota (opcional, igual para todas)",
    )

    def clean(self):
        cleaned = super().clean()
        condominio = cleaned.get("condominio")
        torre = cleaned.get("torre")
        desde = cleaned.get("desde")
        hasta = cleaned.get("hasta")
        if torre and condominio and torre.condominio_id != condominio.id:
            raise forms.ValidationError("Esa torre no pertenece al condominio elegido.")
        if desde is not None and hasta is not None:
            if hasta < desde:
                raise forms.ValidationError("El número final no puede ser menor que el inicial.")
            if (hasta - desde + 1) > self.MAX_UNIDADES_POR_LOTE:
                raise forms.ValidationError(f"Como máximo {self.MAX_UNIDADES_POR_LOTE} unidades por lote.")
        return cleaned


@admin.register(Unidad)
class UnidadAdmin(ModelAdmin):
    list_display = ["numero", "calle", "condominio", "torre_display", "alicuota"]
    list_filter = [("condominio", AutocompleteSelectFilter), ("torre", AutocompleteSelectFilter)]
    list_filter_submit = True
    search_fields = ["numero", "calle", "torre__nombre", "condominio__nombre"]
    actions_list = ["crear_unidades_en_lote"]
    list_select_related = ["condominio", "torre"]
    # Con varios condominios reales, el desplegable de torre mostraba TODAS
    # las de TODOS los condominios en una sola lista plana (ver
    # Torre.__str__, que agrega el condominio entre paréntesis justo porque
    # se mezclan) -- con autocomplete se busca escribiendo en vez de
    # desplazarse por cientos de opciones. El guardado también queda
    # protegido aunque se elija mal (ver Unidad.clean()).
    autocomplete_fields = ["condominio", "torre"]

    @admin.display(description="Torre", ordering="torre__nombre")
    def torre_display(self, obj):
        # Antes mostraba "-" para una unidad sin torre -- ambiguo (¿no tiene
        # torre, o nadie la cargó?). Mostrar la etiqueta_unidad del propio
        # condominio (ej. "Casa") deja claro que es así a propósito, sin
        # inventar un texto fijo que no calce con cómo le dice cada cliente
        # a sus unidades.
        if obj.torre_id:
            return obj.torre.nombre
        return obj.condominio.etiqueta_unidad

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _torre_len=Length("torre__nombre"), _num_len=Length("numero"),
        ).order_by("condominio__nombre", "_torre_len", "torre__nombre", "_num_len", "numero")

    def get_changelist(self, request, **kwargs):
        return ChangeListOrdenAnotado

    @action(
        description="Crear unidades en lote",
        icon="add_box",
        url_path="crear-unidades-en-lote",
        dialog={
            "title": "Crear unidades en lote",
            "description": "Crea varias unidades numeradas de una vez (ej. del 101 al 115), en vez de una por una.",
            "form_class": CrearUnidadesEnLoteForm,
            "form_submit_text": "Crear",
        },
    )
    def crear_unidades_en_lote(self, request, form):
        condominio = form.cleaned_data["condominio"]
        torre = form.cleaned_data["torre"]
        calle = form.cleaned_data["calle"] or ""
        prefijo = form.cleaned_data["prefijo"] or ""
        alicuota = form.cleaned_data["alicuota"]

        creadas = 0
        ya_existian = 0
        for n in range(form.cleaned_data["desde"], form.cleaned_data["hasta"] + 1):
            numero = f"{prefijo}{n}"
            defaults = {"alicuota": alicuota} if alicuota is not None else {}
            _, creada = Unidad.objects.get_or_create(condominio=condominio, torre=torre, numero=numero, calle=calle, defaults=defaults)
            if creada:
                creadas += 1
            else:
                ya_existian += 1

        if creadas:
            mensaje = f"Se crearon {creadas} unidades nuevas en {condominio}."
            if ya_existian:
                mensaje += f" {ya_existian} ya existían y se omitieron."
            messages.success(request, mensaje)
        else:
            messages.warning(request, f"No se creó ninguna unidad nueva -- las {ya_existian} del rango ya existían.")
        return redirect("admin:core_unidad_changelist")


class SinUnidadFilter(admin.SimpleListFilter):
    """Mismo filtro que SinCondominioFilter (ver más abajo, Usuarios) pero
    para el otro lado de la relación opcional: Membresia.unidad es nula
    para directiva/administración/conserjería (no les aplica) y también,
    por error, para algún residente al que se le haya olvidado asignar
    depto -- esto deja encontrar esos casos sin tener que revisar fila por
    fila."""

    title = "unidad asignada"
    parameter_name = "con_unidad"

    def lookups(self, request, model_admin):
        return [("no", "Sin unidad asignada"), ("si", "Con unidad asignada")]

    def queryset(self, request, queryset):
        if self.value() == "no":
            return queryset.filter(unidad__isnull=True)
        if self.value() == "si":
            return queryset.filter(unidad__isnull=False)
        return queryset


@admin.register(Membresia)
class MembresiaAdmin(ModelAdmin):
    """Filtros como desplegable con buscador (AutocompleteSelectFilter) en vez
    de la lista larga de links que da el filtro por defecto -- con 27+
    condominios/cientos de unidades y subiendo, esa lista ya no es manejable.
    Orden de los filtros: de lo más amplio (condominio) a lo más puntual
    (block, depto), con el rol aparte al final por ser un atributo
    transversal, no parte de esa jerarquía."""

    list_display = ["user", "condominio", "rol_badge", "unidad"]
    list_filter = [
        ("condominio", AutocompleteSelectFilter),
        ("unidad__torre", AutocompleteSelectFilter),
        ("unidad", AutocompleteSelectFilter),
        SinUnidadFilter,
        "rol",
    ]
    list_filter_submit = True
    autocomplete_fields = ["user", "unidad"]
    list_select_related = ["user", "condominio", "unidad", "unidad__torre", "unidad__condominio"]

    @display(description="Rol", ordering="rol", label={"residente": "success", "delegado": "secondary"})
    def rol_badge(self, obj):
        return obj.rol, obj.get_rol_display()

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _torre_len=Length("unidad__torre__nombre"), _num_len=Length("unidad__numero"),
        ).order_by("condominio__nombre", "_torre_len", "unidad__torre__nombre", "_num_len", "unidad__numero", "rol", "user__username")

    def get_changelist(self, request, **kwargs):
        return ChangeListOrdenAnotado


@admin.action(description="Marcar como atendido")
def marcar_atendido(modeladmin, request, queryset):
    queryset.update(atendido=True)


@admin.register(SolicitudAcceso)
class SolicitudAccesoAdmin(ModelAdmin):
    list_display = ["condominio", "nombre", "comuna", "telefono", "atendido", "fecha_creacion"]
    list_filter = ["atendido", "comuna"]
    search_fields = ["nombre", "condominio", "telefono", "email"]
    actions = [marcar_atendido]


@admin.action(description="Marcar como atendida (avisa por correo)")
def marcar_atendida(modeladmin, request, queryset):
    from .views import enviar_correo_eliminacion_confirmada

    for solicitud in queryset.filter(atendida=False):
        solicitud.atendida = True
        solicitud.fecha_atencion = timezone.now()
        solicitud.save(update_fields=["atendida", "fecha_atencion"])
        enviar_correo_eliminacion_confirmada(solicitud)


@admin.register(SolicitudEliminacion)
class SolicitudEliminacionAdmin(ModelAdmin):
    list_display = ["nombre", "username", "email", "condominio_nombre", "atendida", "fecha_creacion"]
    list_filter = ["atendida"]
    search_fields = ["nombre", "username", "email", "condominio_nombre"]
    readonly_fields = ["membresia", "nombre", "username", "email", "condominio_nombre", "motivo", "fecha_creacion"]
    actions = [marcar_atendida]


# auth.User/auth.Group traían el admin de Django sin tocar (nunca se
# reemplazaron) -- Unfold reemplaza las plantillas globales del admin, pero
# el formulario de "Añadir usuario" seguía usando los widgets planos de
# Django para password1/password2, incompatibles con el JS que Unfold
# espera en esos campos dentro de su propio tema: el botón "Guardar" no
# hacía nada (bug real reportado por el usuario). unfold.forms ya trae
# UserCreationForm/UserChangeForm/AdminPasswordChangeForm armados con los
# widgets correctos -- solo había que reenganchar el ModelAdmin con ellos.
admin.site.unregister(User)
admin.site.unregister(Group)


class SinCondominioFilter(admin.SimpleListFilter):
    """Para encontrar cuentas creadas en /admin/auth/user/add/ (ver
    UserAdmin) a las que todavía les falta la Membresia que las liga a un
    condominio -- sin esto no hay forma rápida de verlas, hay que revisar
    usuario por usuario si tienen membresia."""

    title = "condominio asignado"
    parameter_name = "con_condominio"

    def lookups(self, request, model_admin):
        return [("no", "Sin condominio asignado"), ("si", "Con condominio asignado")]

    def queryset(self, request, queryset):
        if self.value() == "no":
            return queryset.filter(membresia__isnull=True)
        if self.value() == "si":
            return queryset.filter(membresia__isnull=False)
        return queryset


class MembresiaInlineParaUsuario(TabularInline):
    """Deja asignar el condominio (y unidad/rol) de un usuario desde su
    propia página, sin tener que ir aparte a Membresías. Solo aparece
    después de guardar el usuario por primera vez -- Django necesita que
    el usuario ya tenga un ID antes de poder ligarlo a un condominio."""

    model = Membresia
    fk_name = "user"
    extra = 1
    max_num = 1
    autocomplete_fields = ["condominio", "unidad"]
    fields = ["condominio", "unidad", "rol"]
    verbose_name = "Membresía"
    verbose_name_plural = "Membresía (condominio asignado)"


class UserCreationFormConMedidor(UserCreationForm):
    """Agrega el medidor de seguridad en vivo (Baja/Media/Alta) bajo el
    campo de contraseña al crear un usuario -- carga el JS vía Media, sin
    tocar el template de Unfold."""

    class Media:
        js = ["core/js/medidor_contrasena.js", "core/js/admin_password_medidor.js"]


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationFormConMedidor
    change_password_form = AdminPasswordChangeForm
    list_filter = (*BaseUserAdmin.list_filter, SinCondominioFilter)
    inlines = [MembresiaInlineParaUsuario]


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass

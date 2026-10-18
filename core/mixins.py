from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.utils import timezone

MENSAJE_SIN_CONDOMINIO = "Tu cuenta no está vinculada a ningún condominio."
DEVQUAD_CONDOMINIO_SESSION_KEY = "devquad_condominio_id"


def condominio_activo_devquad(request):
    """Condominio que un devquad (is_staff, sin Membresia propia) eligió
    operar en esta sesión -- ver DevquadCondominiosView/
    DevquadEntrarCondominioView en core/views.py. None si todavía no
    eligió ninguno, o si el que tenía guardado ya no existe (se borró,
    o la sesión quedó con un id viejo)."""
    from .models import Condominio

    condominio_id = request.session.get(DEVQUAD_CONDOMINIO_SESSION_KEY)
    if not condominio_id:
        return None
    return Condominio.objects.filter(pk=condominio_id).first()


class CondominioRequiredMixin(LoginRequiredMixin):
    """Exige login y restringe las consultas al condominio del usuario logueado.

    A diferencia de NegocioRequiredMixin en PataAgenda, acá no hace falta
    resolver una "sucursal activa" por Membresia -- un residente/delegado
    pertenece a un solo condominio. La excepción es devquad (is_staff, sin
    Membresia propia): opera sobre CUALQUIER condominio, uno a la vez,
    elegido en `DevquadCondominiosView` y guardado en la sesión (ver
    condominio_activo_devquad arriba) -- en ese caso self.membresia queda
    en None, así que cualquier código que dependa de self.membresia.rol/
    .unidad debe tolerar ese caso (ver SoloStaffMixin, que resuelve el
    permiso por is_staff y nunca llega a tocar self.membresia).
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            membresia = getattr(request.user, "membresia", None)
            if membresia is None:
                if request.user.is_staff:
                    condominio = condominio_activo_devquad(request)
                    if condominio is None:
                        return redirect("devquad-condominios")
                    if not condominio.puede_operar:
                        return redirect("cuenta-desactivada")
                    self.membresia = None
                    self.condominio = condominio
                    return super().dispatch(request, *args, **kwargs)
                messages.error(request, MENSAJE_SIN_CONDOMINIO)
                return redirect("login")
            if not membresia.condominio.puede_operar:
                return redirect("cuenta-desactivada")
            if not membresia.terminos_aceptados_en:
                return redirect("aceptar-terminos")
            self.membresia = membresia
            self.condominio = membresia.condominio
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().filter(condominio=self.condominio)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["membresia"] = self.membresia
        context["condominio"] = self.condominio
        return context


class CondominioFormMixin(CondominioRequiredMixin):
    """Para crear/editar: asigna el condominio a la instancia antes de guardar."""

    def form_valid(self, form):
        form.instance.condominio = self.condominio
        return super().form_valid(form)


class SoloDirectivaMixin:
    """Mezclar ANTES de CondominioRequiredMixin/CondominioFormMixin: exige rol 'directiva' exacto.

    Uso deliberadamente angosto: solo para lo que es "configuración de fondo"
    de la directiva (Mi condominio, regenerar el link de autoregistro) -- no
    para tareas operativas del día a día, que le corresponden a Administración
    también (ver EsDirectivaOAdministracionMixin).
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            membresia = getattr(request.user, "membresia", None)
            if membresia and membresia.rol != "directiva":
                messages.error(request, "Esta acción es exclusiva de la directiva.")
                return redirect("inicio")
        return super().dispatch(request, *args, **kwargs)


class EsDirectivaOAdministracionMixin:
    """Mezclar ANTES de CondominioRequiredMixin/CondominioFormMixin: tareas operativas del
    día a día (miembros, torres, unidades, gastos comunes) -- directiva supervisa y también
    puede hacerlas, administración las hace en el día a día."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            membresia = getattr(request.user, "membresia", None)
            if membresia and membresia.rol not in ("directiva", "administracion"):
                messages.error(request, "Esta acción es exclusiva de la directiva/administración.")
                return redirect("inicio")
        return super().dispatch(request, *args, **kwargs)


class SoloAdministracionMixin:
    """Mezclar ANTES de CondominioRequiredMixin/CondominioFormMixin: exige rol
    'administracion' exacto -- ni siquiera directiva pasa.

    Uso deliberadamente angosto: solo para generar un gasto común nuevo
    (fijar el monto del periodo), que el usuario pidió dejar exclusivo de
    administración. El resto de gastos comunes (ver la lista, marcar cuotas
    pagadas) sigue abierto a directiva también, ver EsDirectivaOAdministracionMixin.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            membresia = getattr(request.user, "membresia", None)
            if membresia and membresia.rol != "administracion":
                messages.error(request, "Esta acción es exclusiva de administración.")
                return redirect("inicio")
        return super().dispatch(request, *args, **kwargs)


class SuscripcionActivaMixin:
    """Mezclar ANTES de CondominioRequiredMixin/CondominioFormMixin: exige que
    la suscripción del condominio esté al día (pagado_hasta en el futuro).

    Uso deliberadamente angosto: solo para las acciones que generan NUEVO
    valor cobrable cada mes -- generar un gasto común nuevo, crear un
    empleado, generar una liquidación -- no para ver o editar lo que ya
    existe (eso sigue disponible aunque venza la suscripción, ver
    SoloAdministracionMixin en cada app para el resto de permisos)."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            membresia = getattr(request.user, "membresia", None)
            if membresia:
                condominio = membresia.condominio
                if not (condominio.pagado_hasta and condominio.pagado_hasta >= timezone.localdate()):
                    messages.error(
                        request,
                        "Esta función requiere que la suscripción esté al día -- puedes pagarla desde el inicio.",
                    )
                    return redirect("inicio")
        return super().dispatch(request, *args, **kwargs)


class EsDirectivaAdministracionOConserjeMixin:
    """Mezclar ANTES de CondominioRequiredMixin/CondominioFormMixin: exige directiva,
    administración o conserjería (ej. accesos)."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            membresia = getattr(request.user, "membresia", None)
            if membresia and membresia.rol not in ("directiva", "administracion", "conserje"):
                messages.error(request, "Esta acción es exclusiva de la directiva/administración/conserjería.")
                return redirect("inicio")
        return super().dispatch(request, *args, **kwargs)


class SoloStaffMixin:
    """Mezclar ANTES de CondominioRequiredMixin/CondominioFormMixin: exige is_staff.

    Uso: operaciones que son de configuración inicial del condominio (crear
    torres) y que hace DevQuad al dar de alta al cliente, no el día a día de
    directiva/administración -- la estructura física del edificio no cambia
    seguido y un cambio mal hecho ahí rompe la numeración de unidades.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_staff:
            messages.error(request, "Esta acción es exclusiva del administrador de la plataforma.")
            return redirect("inicio")
        return super().dispatch(request, *args, **kwargs)


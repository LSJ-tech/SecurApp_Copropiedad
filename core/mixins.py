from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect

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
                respuesta = self._dispatch_sin_membresia(request)
            else:
                respuesta = self._dispatch_con_membresia(membresia)
            if respuesta is not None:
                return respuesta
        return super().dispatch(request, *args, **kwargs)

    def _dispatch_sin_membresia(self, request):
        """Caso devquad (is_staff, sin Membresia propia) -- None si puede
        seguir, o la respuesta a devolver directo si no."""
        if not request.user.is_staff:
            messages.error(request, MENSAJE_SIN_CONDOMINIO)
            return redirect("login")
        condominio = condominio_activo_devquad(request)
        if condominio is None:
            return redirect("devquad-condominios")
        if not condominio.puede_operar:
            return redirect("cuenta-desactivada")
        self.membresia = None
        self.condominio = condominio
        return None

    def _dispatch_con_membresia(self, membresia):
        """Caso residente/delegado -- None si puede seguir, o la respuesta
        a devolver directo si no."""
        if not membresia.condominio.puede_operar:
            return redirect("cuenta-desactivada")
        if not membresia.terminos_aceptados_en:
            return redirect("aceptar-terminos")
        self.membresia = membresia
        self.condominio = membresia.condominio
        return None

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


class SoloStaffMixin:
    """Mezclar ANTES de CondominioRequiredMixin/CondominioFormMixin: exige is_staff.

    Uso: cualquier tarea de gestión de un condominio (miembros, torres,
    unidades, avisos, Mi condominio) -- devquad es la única cuenta que las
    hace, no hay un rol de Membresia con estos permisos."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_staff:
            messages.error(request, "Esta acción es exclusiva del administrador de la plataforma.")
            return redirect("inicio")
        return super().dispatch(request, *args, **kwargs)


import pygeohash as pgh
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.views.generic import FormView, TemplateView

from core.usuarios import generar_username

from .forms import RegistroVecinoForm
from .models import PRECISION_GEOHASH, PerfilGeografico


class RegistroVecinoView(FormView):
    """Autoregistro público a la red vecinal geográfica -- sin condominio,
    sin código de invitación (ver RegistroVecinoForm). Mismo patrón que
    RegistroResidenteView: usuario generado, contraseña elegida por la
    persona, login inmediato, sin verificación de email/teléfono en esta
    fase."""

    template_name = "vecindario/registro_vecino.html"
    form_class = RegistroVecinoForm

    def form_valid(self, form):
        datos = form.cleaned_data
        username = generar_username(datos["nombre"], datos["apellido"])
        geohash = pgh.encode(float(datos["lat"]), float(datos["lng"]), precision=PRECISION_GEOHASH)

        user = User.objects.create_user(
            username=username, password=datos["password1"], email=datos.get("email", ""),
            first_name=datos["nombre"], last_name=datos["apellido"],
        )
        PerfilGeografico.objects.create(
            user=user, direccion_texto=datos["direccion_texto"], lat=datos["lat"], lng=datos["lng"],
            region=datos["region"], comuna=datos["comuna"], geohash=geohash, telefono=datos["telefono"],
        )
        login(self.request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(
            self.request,
            f"¡Bienvenido a la red vecinal de {datos['comuna']}! Tu usuario es «{username}» — anótalo, lo "
            f"necesitas para volver a entrar. Desde aquí puedes activar el botón de pánico y avisar a tu barrio.",
        )
        return redirect("mi-barrio")


class MiBarrioView(LoginRequiredMixin, TemplateView):
    """Dashboard simplificado para quien no tiene Membresia (no pertenece a
    ningún condominio) -- botón de pánico geográfico, sin nada de gastos
    comunes/accesos/avisos. Si el usuario SÍ tiene Membresia, usa el
    dashboard normal (InicioView), no esta página."""

    template_name = "vecindario/mi_barrio.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and getattr(request.user, "perfil_geografico", None) is None:
            if getattr(request.user, "membresia", None) is not None:
                return redirect("inicio")
            messages.error(request, "Tu cuenta todavía no está registrada en la red vecinal.")
            return redirect("vecindario-registro")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["perfil"] = self.request.user.perfil_geografico
        return context

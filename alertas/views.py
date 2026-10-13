from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView

from core.mixins import CondominioFormMixin, CondominioRequiredMixin, EsDirectivaOAdministracionMixin
from core.models import REGION_CHOICES

from .empresas_servicios import EMPRESAS_SUGERIDAS_POR_REGION
from .forms import NumeroEmergenciaForm
from .models import NUMEROS_NACIONALES, Alerta, NumeroEmergencia


class AlertaHistorialView(CondominioRequiredMixin, ListView):
    """Historial completo de alertas del condominio -- abierto a cualquier rol,
    igual que resolver/ver el mapa (ver EsDirectivaOAdministracionMixin para lo
    que sí sigue restringido por rol)."""

    template_name = "alertas/alerta_historial.html"
    context_object_name = "alertas"
    paginate_by = 20

    def get_queryset(self):
        qs = Alerta.objects.filter(condominio_id__in=self.condominio.ids_red_alertas).select_related(
            "condominio", "autor__user", "autor__unidad__torre", "autor__condominio",
            "resuelta_por__user", "resuelta_por__unidad__torre", "resuelta_por__condominio",
        )
        estado = self.request.GET.get("estado")
        if estado:
            qs = qs.filter(estado=estado)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["estado_seleccionado"] = self.request.GET.get("estado", "")
        return context


class NumeroEmergenciaListView(CondominioRequiredMixin, ListView):
    """Abierto a cualquier rol -- agregar/borrar sí queda restringido a
    directiva/administración (ver NumeroEmergenciaCreateView/EliminarNumeroEmergenciaView).

    Precarga los 4 números nacionales (estables, no dependen de la comuna)
    la primera vez que alguien entra -- si el condominio ya tiene números
    cargados no se toca nada, para no resucitar uno que directiva haya
    borrado a propósito."""

    template_name = "alertas/numero_emergencia_list.html"
    context_object_name = "numeros"

    def get_queryset(self):
        if not NumeroEmergencia.objects.filter(condominio=self.condominio).exists():
            NumeroEmergencia.objects.bulk_create([
                NumeroEmergencia(condominio=self.condominio, categoria=categoria, nombre=nombre, telefono=telefono)
                for categoria, nombre, telefono in NUMEROS_NACIONALES
            ])
        return NumeroEmergencia.objects.filter(condominio=self.condominio)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sugerencias"] = EMPRESAS_SUGERIDAS_POR_REGION.get(self.condominio.region, {})
        # Condominio.region guarda la clave (ej. "valparaiso"), no el nombre
        # -- no tiene choices= en el modelo (lo valida el form al crear el
        # condominio), así que no existe get_region_display().
        context["region_nombre"] = dict(REGION_CHOICES).get(self.condominio.region, self.condominio.region)
        return context


class NumeroEmergenciaCreateView(EsDirectivaOAdministracionMixin, CondominioFormMixin, CreateView):
    model = NumeroEmergencia
    form_class = NumeroEmergenciaForm
    template_name = "alertas/numero_emergencia_form.html"
    success_url = reverse_lazy("numeros-emergencia")

    def get_initial(self):
        """Pre-llena nombre/categoría al venir de una sugerencia por región
        (ver numero_emergencia_list.html) -- el teléfono siempre queda vacío,
        nunca se sugiere uno (ver alertas/empresas_servicios.py)."""
        initial = super().get_initial()
        nombre = self.request.GET.get("nombre")
        categoria = self.request.GET.get("categoria")
        if nombre:
            initial["nombre"] = nombre
        if categoria:
            initial["categoria"] = categoria
        return initial


class EliminarNumeroEmergenciaView(EsDirectivaOAdministracionMixin, CondominioRequiredMixin, View):
    def post(self, request, pk):
        numero = get_object_or_404(NumeroEmergencia, pk=pk, condominio=self.condominio)
        numero.delete()
        return redirect("numeros-emergencia")

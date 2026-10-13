from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, ListView

from core.mixins import CondominioFormMixin, CondominioRequiredMixin, EsDirectivaOAdministracionMixin
from core.models import REGION_CHOICES

from .empresas_servicios import EMPRESAS_SUGERIDAS_POR_REGION
from .forms import NumeroEmergenciaForm, PropuestaNumeroEmergenciaForm
from .models import NUMEROS_NACIONALES, Alerta, NumeroEmergencia, PropuestaNumeroEmergencia


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
    """Abierto a cualquier rol -- agregar sí queda restringido a directiva/
    administración (ver NumeroEmergenciaCreateView) y borrar queda
    restringido además a los que no son nacionales (ver
    EliminarNumeroEmergenciaView y NumeroEmergencia.es_nacional).

    Sincroniza los números nacionales en cada visita (get_or_create, no
    pisa lo que ya existe) -- como nadie puede borrarlos, no hay riesgo de
    "resucitar" algo borrado a propósito, así que si más adelante se
    amplía NUMEROS_NACIONALES, todos los condominios quedan al día solos,
    sin backfill."""

    template_name = "alertas/numero_emergencia_list.html"
    context_object_name = "numeros"

    def get_queryset(self):
        for categoria, nombre, telefono in NUMEROS_NACIONALES:
            NumeroEmergencia.objects.get_or_create(
                condominio=self.condominio, nombre=nombre, defaults={"categoria": categoria, "telefono": telefono},
            )
        return NumeroEmergencia.objects.filter(condominio=self.condominio)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sugerencias"] = EMPRESAS_SUGERIDAS_POR_REGION.get(self.condominio.region, {})
        # Condominio.region guarda la clave (ej. "valparaiso"), no el nombre
        # -- no tiene choices= en el modelo (lo valida el form al crear el
        # condominio), así que no existe get_region_display().
        context["region_nombre"] = dict(REGION_CHOICES).get(self.condominio.region, self.condominio.region)
        if self.membresia.rol in ("directiva", "administracion"):
            context["propuestas_pendientes"] = PropuestaNumeroEmergencia.objects.filter(
                condominio=self.condominio, estado="pendiente",
            ).select_related("autor__user")
        context["mis_propuestas"] = PropuestaNumeroEmergencia.objects.filter(
            condominio=self.condominio, autor=self.membresia,
        )
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
        if numero.es_nacional:
            messages.error(request, "Los números nacionales (Carabineros, Bomberos, etc.) no se pueden eliminar.")
            return redirect("numeros-emergencia")
        numero.delete()
        return redirect("numeros-emergencia")


class ProponerNumeroEmergenciaView(CondominioFormMixin, CreateView):
    """Abierto a cualquier rol -- a diferencia de NumeroEmergenciaCreateView
    (directiva/administración, directo), esto queda "Pendiente" hasta que
    directiva/administración lo apruebe o rechace (ver
    AprobarPropuestaNumeroEmergenciaView/RechazarPropuestaNumeroEmergenciaView)."""

    model = PropuestaNumeroEmergencia
    form_class = PropuestaNumeroEmergenciaForm
    template_name = "alertas/propuesta_numero_emergencia_form.html"
    success_url = reverse_lazy("numeros-emergencia")

    def form_valid(self, form):
        form.instance.autor = self.membresia
        messages.success(self.request, "Gracias, tu propuesta quedó pendiente de revisión por directiva/administración.")
        return super().form_valid(form)


class AprobarPropuestaNumeroEmergenciaView(EsDirectivaOAdministracionMixin, CondominioRequiredMixin, View):
    def post(self, request, pk):
        propuesta = get_object_or_404(PropuestaNumeroEmergencia, pk=pk, condominio=self.condominio, estado="pendiente")
        NumeroEmergencia.objects.create(
            condominio=self.condominio, categoria=propuesta.categoria, nombre=propuesta.nombre, telefono=propuesta.telefono,
        )
        propuesta.estado = "aprobada"
        propuesta.revisada_por = self.membresia
        propuesta.fecha_revision = timezone.now()
        propuesta.save(update_fields=["estado", "revisada_por", "fecha_revision"])
        messages.success(request, f"«{propuesta.nombre}» se agregó a los números de emergencia.")
        return redirect("numeros-emergencia")


class RechazarPropuestaNumeroEmergenciaView(EsDirectivaOAdministracionMixin, CondominioRequiredMixin, View):
    def post(self, request, pk):
        propuesta = get_object_or_404(PropuestaNumeroEmergencia, pk=pk, condominio=self.condominio, estado="pendiente")
        propuesta.estado = "rechazada"
        propuesta.revisada_por = self.membresia
        propuesta.fecha_revision = timezone.now()
        propuesta.save(update_fields=["estado", "revisada_por", "fecha_revision"])
        return redirect("numeros-emergencia")

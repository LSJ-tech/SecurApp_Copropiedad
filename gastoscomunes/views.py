import calendar
from datetime import date

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Prefetch
from django.db.models.functions import Length
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, ListView, UpdateView, View

from core.forms import CondominioForm
from core.mixins import CondominioFormMixin, CondominioRequiredMixin, EsDirectivaOAdministracionMixin, SoloAdministracionMixin, SuscripcionActivaMixin
from core.models import Condominio, Membresia, Torre

from .boucher import enviar_boucher_por_correo, generar_boucher_pdf
from .forms import GastoComunForm
from .models import CuotaUnidad, GastoComun
from .reportes import generar_cuotas_excel, generar_cuotas_pdf


def _cuotas_del_gasto(condominio, gasto_pk, torre_id=None):
    qs = CuotaUnidad.objects.filter(
        gasto_comun__condominio=condominio, gasto_comun_id=gasto_pk
    ).select_related("unidad", "unidad__torre", "gasto_comun")
    if torre_id:
        qs = qs.filter(unidad__torre_id=torre_id)
    return qs.annotate(_torre_len=Length("unidad__torre__nombre")).order_by("_torre_len", "unidad__torre__nombre", "unidad__numero")


class GastoComunListView(EsDirectivaOAdministracionMixin, CondominioFormMixin, ListView):
    model = GastoComun
    template_name = "gastoscomunes/gasto_list.html"
    context_object_name = "gastos"


class GastoComunCreateView(SoloAdministracionMixin, SuscripcionActivaMixin, CondominioFormMixin, CreateView):
    model = GastoComun
    form_class = GastoComunForm
    template_name = "gastoscomunes/gasto_form.html"
    success_url = reverse_lazy("gastos-comunes-list")

    def form_valid(self, form):
        if form.cleaned_data["modo"] == "por_unidad":
            num_unidades = self.condominio.unidades.count()
            form.instance.monto_total = form.cleaned_data["monto_por_unidad"] * num_unidades
        else:
            form.instance.monto_por_unidad = None

        anio, mes = map(int, form.cleaned_data["periodo"].split("-"))
        ultimo_dia = calendar.monthrange(anio, mes)[1]
        form.instance.fecha_vencimiento = date(anio, mes, ultimo_dia)

        response = super().form_valid(form)
        self.object.generar_cuotas()
        return response


class DatosTransferenciaUpdateView(SoloAdministracionMixin, CondominioFormMixin, UpdateView):
    """Banco/cuenta/RUT que se muestra a los residentes para pagar gastos
    comunes -- exclusivo de administración, igual que generar el gasto
    común (a pedido del usuario; antes vivía en "Mi condominio", exclusivo
    de directiva)."""

    model = Condominio
    form_class = CondominioForm
    template_name = "gastoscomunes/datos_transferencia_form.html"
    success_url = reverse_lazy("gastos-comunes-list")

    def get_object(self, queryset=None):
        return self.condominio


class CuotaListView(EsDirectivaOAdministracionMixin, CondominioRequiredMixin, ListView):
    template_name = "gastoscomunes/cuota_list.html"
    context_object_name = "cuotas"
    paginate_by = 50

    def get_queryset(self):
        residentes_con_correo = Membresia.objects.filter(rol="residente").exclude(user__email="").select_related("user")
        qs = _cuotas_del_gasto(self.condominio, self.kwargs["gasto_pk"], self.request.GET.get("torre"))
        return qs.prefetch_related(Prefetch("unidad__membresias", queryset=residentes_con_correo, to_attr="residentes_con_correo"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["gasto"] = get_object_or_404(GastoComun, pk=self.kwargs["gasto_pk"], condominio=self.condominio)
        context["gastos"] = GastoComun.objects.filter(condominio=self.condominio).order_by("-periodo")
        context["torres"] = Torre.objects.filter(condominio=self.condominio).annotate(_len=Length("nombre")).order_by("_len", "nombre")
        context["torre_seleccionada"] = self.request.GET.get("torre", "")
        return context


class CuotasExportarExcelView(EsDirectivaOAdministracionMixin, CondominioRequiredMixin, View):
    def get(self, request, gasto_pk):
        gasto = get_object_or_404(GastoComun, pk=gasto_pk, condominio=self.condominio)
        cuotas = _cuotas_del_gasto(self.condominio, gasto_pk, request.GET.get("torre"))
        return generar_cuotas_excel(gasto, cuotas, self.condominio)


class CuotasExportarPDFView(EsDirectivaOAdministracionMixin, CondominioRequiredMixin, View):
    def get(self, request, gasto_pk):
        gasto = get_object_or_404(GastoComun, pk=gasto_pk, condominio=self.condominio)
        cuotas = _cuotas_del_gasto(self.condominio, gasto_pk, request.GET.get("torre"))
        return generar_cuotas_pdf(gasto, cuotas, self.condominio)


class MarcarCuotaPagadaView(EsDirectivaOAdministracionMixin, CondominioRequiredMixin, View):
    def post(self, request, pk):
        cuota = get_object_or_404(
            CuotaUnidad.objects.select_related("unidad", "unidad__torre", "gasto_comun", "gasto_comun__condominio"),
            pk=pk, gasto_comun__condominio=self.condominio,
        )
        cuota.estado = "pagado"
        cuota.fecha_pago = timezone.localdate()
        cuota.save()
        correo_destino = request.POST.get("correo_destino", "").strip()
        if correo_destino:
            try:
                validate_email(correo_destino)
            except ValidationError:
                pass
            else:
                enviar_boucher_por_correo(cuota, correo_destino)
        return redirect("gastos-comunes-cuotas", gasto_pk=cuota.gasto_comun_id)


class BoucherPDFView(CondominioRequiredMixin, View):
    """Comprobante de pago descargable -- el residente solo ve el de su propia
    unidad, directiva/administración ven el de cualquiera en su condominio."""

    def get(self, request, pk):
        cuota = get_object_or_404(
            CuotaUnidad.objects.select_related("unidad", "unidad__torre", "gasto_comun", "gasto_comun__condominio"),
            pk=pk, gasto_comun__condominio=self.condominio,
        )
        es_gestion = self.membresia.rol in ("directiva", "administracion")
        es_propia = self.membresia.unidad_id == cuota.unidad_id
        if not (es_gestion or es_propia):
            messages.error(request, "No puedes ver el comprobante de otra unidad.")
            return redirect("inicio")
        if cuota.estado != "pagado":
            messages.error(request, "Esta cuota todavía no está pagada.")
            return redirect("gastos-comunes-cuotas", gasto_pk=cuota.gasto_comun_id) if es_gestion else redirect("mis-cuotas")
        return generar_boucher_pdf(cuota)


class MisCuotasView(CondominioRequiredMixin, ListView):
    """Vista del residente para sus propias cuotas -- antes solo existía por API (pensada para la futura app móvil)."""

    template_name = "gastoscomunes/mis_cuotas.html"
    context_object_name = "cuotas"

    def get_queryset(self):
        if self.membresia.unidad_id is None:
            return CuotaUnidad.objects.none()
        return CuotaUnidad.objects.filter(unidad=self.membresia.unidad).select_related("gasto_comun").order_by("-gasto_comun__fecha_emision")

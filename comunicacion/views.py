from django.views.generic import TemplateView

from core.mixins import CondominioRequiredMixin


class MuroVecinosView(CondominioRequiredMixin, TemplateView):
    """Muro de vecinos -- cualquier rol puede publicar (a diferencia de
    Avisos, que es solo directiva/administración). La lista y el formulario
    viven en JS contra /api/v1/muro/, igual que Avisos/Alertas en el inicio,
    así que acá no hay queryset."""

    template_name = "comunicacion/muro.html"

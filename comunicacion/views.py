from django.views.generic import TemplateView

from core.mixins import CondominioRequiredMixin


class MuroVecinosView(CondominioRequiredMixin, TemplateView):
    """Muro de vecinos -- cualquier rol puede publicar (a diferencia de
    Avisos, que es solo directiva/administración). La lista y el formulario
    viven en JS contra /api/v1/muro/, igual que Avisos/Alertas en el inicio,
    así que acá no hay queryset."""

    template_name = "comunicacion/muro.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # La opción "solo mi torre" solo tiene sentido para quien de verdad
        # tiene una torre (residente de un condominio con torres) -- en
        # modo casas, o sin unidad asignada todavía, no se muestra.
        context["torre_propia"] = self.membresia.unidad.torre if self.membresia.unidad_id else None
        return context

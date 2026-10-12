from django.utils import timezone

from .models import Condominio, Membresia, SolicitudAcceso, Unidad


def dashboard_callback(request, context):
    """UNFOLD["DASHBOARD_CALLBACK"] -- arma los datos que pinta
    core/templates/admin/index.html (KPIs + tablas) arriba de la grilla de
    apps de siempre. Solo lectura, nada de esto se usa para filtrar ni
    restringir nada -- es un resumen para quien administra la plataforma
    (DevQuad), no cambia el aislamiento multi-tenant del resto del sistema."""
    from alertas.models import Alerta

    hoy = timezone.localdate()
    condominios = Condominio.objects.all()

    context["kpi_condominios_activos"] = condominios.filter(activo=True).count()
    context["kpi_condominios_total"] = condominios.count()
    context["kpi_unidades"] = Unidad.objects.count()
    context["kpi_miembros"] = Membresia.objects.count()
    context["kpi_alertas_activas"] = Alerta.objects.filter(estado="activa").count()
    context["kpi_solicitudes_pendientes"] = SolicitudAcceso.objects.filter(atendido=False).count()
    context["kpi_suscripciones_vencidas"] = condominios.filter(pagado_hasta__lt=hoy).count()

    filas_condominios = []
    for c in condominios.order_by("-fecha_creacion")[:6]:
        if c.pagado_hasta is None:
            suscripcion = "Sin restricción"
        elif c.pagado_hasta >= hoy:
            suscripcion = f"Vigente hasta {c.pagado_hasta:%d-%m-%Y}"
        else:
            suscripcion = f"Vencida ({c.pagado_hasta:%d-%m-%Y})"
        filas_condominios.append([c.nombre, c.get_plan_display(), c.fecha_creacion.strftime("%d-%m-%Y"), suscripcion])
    context["tabla_condominios_recientes"] = {
        "headers": ["Condominio", "Plan", "Registrado", "Suscripción"],
        "rows": filas_condominios,
    }

    filas_solicitudes = [
        [s.nombre, s.condominio, s.telefono, s.fecha_creacion.strftime("%d-%m-%Y")]
        for s in SolicitudAcceso.objects.filter(atendido=False).order_by("-fecha_creacion")[:6]
    ]
    context["tabla_solicitudes_pendientes"] = {
        "headers": ["Nombre", "Condominio", "Teléfono", "Fecha"],
        "rows": filas_solicitudes,
    }

    return context

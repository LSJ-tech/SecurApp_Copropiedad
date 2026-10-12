import datetime
import json

from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils import timezone

from .models import Condominio, Membresia, SolicitudAcceso, Unidad

NOMBRES_MES = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _ultimos_n_meses(n):
    """[(año, mes), ...] de los últimos n meses, terminando en el actual --
    sin dateutil, solo restando mes a mes con acarreo de año manual."""
    hoy = timezone.localdate()
    anio, mes = hoy.year, hoy.month
    meses = []
    for _ in range(n):
        meses.append((anio, mes))
        mes -= 1
        if mes == 0:
            mes, anio = 12, anio - 1
    return list(reversed(meses))


def dashboard_callback(_request, context):
    """UNFOLD["DASHBOARD_CALLBACK"] -- arma los datos que pinta
    core/templates/admin/index.html (KPIs + tablas) arriba de la grilla de
    apps de siempre. Solo lectura, nada de esto se usa para filtrar ni
    restringir nada -- es un resumen para quien administra la plataforma
    (DevQuad), no cambia el aislamiento multi-tenant del resto del sistema.

    _request: Unfold siempre llama este callback como callback(request, context)
    (posicional, ver AdminSite.index en unfold/sites.py) -- el parámetro es
    obligatorio por ese contrato aunque nunca se use acá."""
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

    meses = _ultimos_n_meses(6)
    inicio = datetime.date(meses[0][0], meses[0][1], 1)
    conteos = (
        condominios.filter(fecha_creacion__date__gte=inicio)
        .annotate(mes=TruncMonth("fecha_creacion"))
        .values("mes")
        .annotate(total=Count("id"))
    )
    conteo_por_mes = {(c["mes"].year, c["mes"].month): c["total"] for c in conteos}
    context["chart_condominios_por_mes"] = json.dumps({
        "labels": [f"{NOMBRES_MES[mes]} {anio}" for anio, mes in meses],
        "datasets": [{
            "label": "Condominios nuevos",
            "data": [conteo_por_mes.get(par, 0) for par in meses],
            "backgroundColor": "#1A2E40",
            "borderRadius": 4,
        }],
    })

    return context

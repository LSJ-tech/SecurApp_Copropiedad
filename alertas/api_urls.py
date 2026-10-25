from rest_framework.routers import DefaultRouter

from .api_views import AlertaViewSet, NumeroEmergenciaViewSet, PropuestaNumeroEmergenciaViewSet

router = DefaultRouter()
router.register("alertas", AlertaViewSet, basename="alerta")
router.register("numeros-emergencia", NumeroEmergenciaViewSet, basename="numero-emergencia")
router.register("propuestas-numero-emergencia", PropuestaNumeroEmergenciaViewSet, basename="propuesta-numero-emergencia")

urlpatterns = router.urls

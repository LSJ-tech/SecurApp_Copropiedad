from rest_framework.routers import DefaultRouter

from .api_views import AlertaViewSet, NumeroEmergenciaViewSet

router = DefaultRouter()
router.register("alertas", AlertaViewSet, basename="alerta")
router.register("numeros-emergencia", NumeroEmergenciaViewSet, basename="numero-emergencia")

urlpatterns = router.urls

from rest_framework.routers import DefaultRouter

from .api_views import AlertaCiudadanaViewSet

router = DefaultRouter()
router.register("vecindario/alertas", AlertaCiudadanaViewSet, basename="alerta-ciudadana")

urlpatterns = router.urls

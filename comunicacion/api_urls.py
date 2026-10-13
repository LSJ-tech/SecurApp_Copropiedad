from rest_framework.routers import DefaultRouter

from .api_views import AvisoViewSet

router = DefaultRouter()
router.register("avisos", AvisoViewSet, basename="aviso")

urlpatterns = router.urls

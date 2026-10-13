from rest_framework.routers import DefaultRouter

from .api_views import AvisoViewSet, PublicacionViewSet

router = DefaultRouter()
router.register("avisos", AvisoViewSet, basename="aviso")
router.register("muro", PublicacionViewSet, basename="publicacion")

urlpatterns = router.urls

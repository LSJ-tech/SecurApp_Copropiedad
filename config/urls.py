from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

API_V1_PREFIX = 'api/v1/'

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', include('core.urls')),
    path('', include('accesos.urls')),
    path('', include('gastoscomunes.urls')),
    path('', include('pagos.urls')),
    path('', include('alertas.urls')),
    path('', include('personal.urls')),
    path('', include('comunicacion.urls')),

    path(API_V1_PREFIX, include('core.api_urls')),
    path(API_V1_PREFIX, include('notificaciones.api_urls')),
    path(API_V1_PREFIX, include('alertas.api_urls')),
    path(API_V1_PREFIX, include('comunicacion.api_urls')),
    path(API_V1_PREFIX, include('gastoscomunes.api_urls')),

    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

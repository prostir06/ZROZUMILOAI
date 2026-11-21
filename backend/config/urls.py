"""URL configuration for ZROZUMILOAI."""
from django.contrib import admin
from django.urls import include, path

from config.health import HealthDetailsView, HealthMetricsView, HealthView
from workspaces.urls import router as workspaces_router

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', HealthView.as_view(), name='api_health'),
    path('api/health/details/', HealthDetailsView.as_view(), name='api_health_details'),
    path('api/health/metrics/', HealthMetricsView.as_view(), name='api_health_metrics'),
    path('api/auth/', include('accounts.urls')),
    path('api/chats/', include('chats.urls')),
    path('api/workspaces/', include('workspaces.urls')),
    path('api/widget/', include('workspaces.widget_urls')),
    path('api/ollama/', include('ollama_proxy.urls')),
    path('api/backups/', include('backups.urls')),
    path('api/', include(workspaces_router.urls)),
]

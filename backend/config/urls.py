"""URL configuration for ZROZUMILOAI."""
from django.contrib import admin
from django.urls import include, path

from config.health import HealthView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', HealthView.as_view(), name='api_health'),
    path('api/auth/', include('accounts.urls')),
    path('api/chats/', include('chats.urls')),
    path('api/workspaces/', include('workspaces.urls')),
    path('api/widget/', include('workspaces.widget_urls')),
    path('api/ollama/', include('ollama_proxy.urls')),
    path('api/backups/', include('backups.urls')),
]

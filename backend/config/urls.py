"""URL configuration for ZROZUMILOAI."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/chats/', include('chats.urls')),
    path('api/workspaces/', include('workspaces.urls')),
    path('api/ollama/', include('ollama_proxy.urls')),
    path('api/backups/', include('backups.urls')),
]

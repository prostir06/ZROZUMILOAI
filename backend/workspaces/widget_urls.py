"""Public widget API routes."""
from django.urls import path

from .widget_views import WidgetChatView, WidgetConfigView

urlpatterns = [
    path('config/', WidgetConfigView.as_view(), name='widget_config'),
    path('chat/', WidgetChatView.as_view(), name='widget_chat'),
]

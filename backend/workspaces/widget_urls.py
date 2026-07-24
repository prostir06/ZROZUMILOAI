"""Public widget API routes."""
from django.urls import path

from .widget_views import (
    WidgetChatView,
    WidgetConfigView,
    WidgetFeedbackView,
)

urlpatterns = [
    path('config/', WidgetConfigView.as_view(), name='widget_config'),
    path('chat/', WidgetChatView.as_view(), name='widget_chat'),
    path(
        'logs/<int:log_id>/feedback/',
        WidgetFeedbackView.as_view(),
        name='widget_chat_log_feedback',
    ),
]

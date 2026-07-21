"""URL routes for chats app."""
from django.urls import path

from .log_views import (
    WorkspaceChatLogClearView,
    WorkspaceChatLogDetailView,
    WorkspaceChatLogExportView,
    WorkspaceChatLogFeedbackView,
    WorkspaceChatLogListView,
)
from .views import ChatDetailView, ChatListCreateView

urlpatterns = [
    path('', ChatListCreateView.as_view(), name='chat_list_create'),
    path('logs/', WorkspaceChatLogListView.as_view(), name='workspace_chat_logs'),
    path('logs/clear/', WorkspaceChatLogClearView.as_view(), name='workspace_chat_logs_clear'),
    path('logs/export/', WorkspaceChatLogExportView.as_view(), name='workspace_chat_logs_export'),
    path(
        'logs/<int:log_id>/feedback/',
        WorkspaceChatLogFeedbackView.as_view(),
        name='workspace_chat_log_feedback',
    ),
    path('logs/<int:log_id>/', WorkspaceChatLogDetailView.as_view(), name='workspace_chat_log_detail'),
    path('<int:chat_id>/', ChatDetailView.as_view(), name='chat_detail'),
]

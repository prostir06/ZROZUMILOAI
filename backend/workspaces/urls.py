"""URL routes for workspaces app."""
from django.urls import path
from rest_framework.routers import DefaultRouter

from chats.analytics_views import (
    WorkspaceAnalyticsExportView,
    WorkspaceAnalyticsView,
    WorkspaceKnowledgeGapResolveView,
)

from .document_views import (
    WorkspaceDocumentDeleteView,
    WorkspaceDocumentListCreateView,
    WorkspaceDocumentRetryView,
    WorkspaceRagStatsView,
)
from .telegram.views import TelegramBotViewSet
from .views import MyWorkspacesView, WorkspaceDetailView, WorkspaceListCreateView
from .widget_views import WidgetTokenDeleteView, WidgetTokenListCreateView

router = DefaultRouter()
router.register(r'telegram-bots', TelegramBotViewSet, basename='telegram-bot')

urlpatterns = [
    path('my/', MyWorkspacesView.as_view(), name='workspace_my'),
    path('', WorkspaceListCreateView.as_view(), name='workspace_list_create'),
    path(
        '<int:workspace_id>/',
        WorkspaceDetailView.as_view(),
        name='workspace_detail',
    ),
    path(
        '<int:workspace_id>/widget-tokens/',
        WidgetTokenListCreateView.as_view(),
        name='workspace_widget_tokens',
    ),
    path(
        '<int:workspace_id>/widget-tokens/<int:token_id>/',
        WidgetTokenDeleteView.as_view(),
        name='workspace_widget_token_delete',
    ),
    path(
        '<int:workspace_id>/documents/',
        WorkspaceDocumentListCreateView.as_view(),
        name='workspace_documents',
    ),
    path(
        '<int:workspace_id>/documents/<int:document_id>/',
        WorkspaceDocumentDeleteView.as_view(),
        name='workspace_document_delete',
    ),
    path(
        '<int:workspace_id>/documents/<int:document_id>/retry/',
        WorkspaceDocumentRetryView.as_view(),
        name='workspace_document_retry',
    ),
    path(
        '<int:workspace_id>/rag-stats/',
        WorkspaceRagStatsView.as_view(),
        name='workspace_rag_stats',
    ),
    path(
        '<int:workspace_id>/analytics/',
        WorkspaceAnalyticsView.as_view(),
        name='workspace_analytics',
    ),
    path(
        '<int:workspace_id>/analytics/export/',
        WorkspaceAnalyticsExportView.as_view(),
        name='workspace_analytics_export',
    ),
    path(
        '<int:workspace_id>/analytics/gaps/<int:log_id>/resolve/',
        WorkspaceKnowledgeGapResolveView.as_view(),
        name='workspace_gap_resolve',
    ),
] + router.urls

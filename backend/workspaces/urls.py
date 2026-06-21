"""URL routes for workspaces app."""
from django.urls import path

from .views import MyWorkspacesView, WorkspaceDetailView, WorkspaceListCreateView
from .document_views import WorkspaceDocumentDeleteView, WorkspaceDocumentListCreateView
from .widget_views import WidgetTokenDeleteView, WidgetTokenListCreateView

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
]

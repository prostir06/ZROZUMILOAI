"""URL routes for workspaces app."""
from django.urls import path

from .views import MyWorkspacesView, WorkspaceDetailView, WorkspaceListCreateView

urlpatterns = [
    path('my/', MyWorkspacesView.as_view(), name='workspace_my'),
    path('', WorkspaceListCreateView.as_view(), name='workspace_list_create'),
    path(
        '<int:workspace_id>/',
        WorkspaceDetailView.as_view(),
        name='workspace_detail',
    ),
]

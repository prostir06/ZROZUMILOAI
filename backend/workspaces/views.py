"""API views for workspaces."""
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Workspace
from .serializers import WorkspaceBriefSerializer, WorkspaceSerializer
from .services import get_user_workspaces


class MyWorkspacesView(APIView):
    """List workspaces available to the current user."""

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        workspaces = get_user_workspaces(request.user)
        serializer = WorkspaceBriefSerializer(workspaces, many=True)
        return Response(serializer.data)


class WorkspaceListCreateView(generics.ListCreateAPIView):
    """List or create workspaces (admin only)."""

    permission_classes = (permissions.IsAdminUser,)
    serializer_class = WorkspaceSerializer
    queryset = Workspace.objects.prefetch_related('users').all()


class WorkspaceDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update or delete a workspace (admin only)."""

    permission_classes = (permissions.IsAdminUser,)
    serializer_class = WorkspaceSerializer
    queryset = Workspace.objects.prefetch_related('users').all()
    lookup_url_kwarg = 'workspace_id'

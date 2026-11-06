"""Workspace analytics API views."""
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chats.analytics_service import get_workspace_analytics
from workspaces.models import Workspace


class WorkspaceAnalyticsView(APIView):
    """
    Get aggregated analytics and KPIs for a specific workspace.

    Access permitted to superusers, staff, and assigned workspace teachers.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id: int):
        """Return analytics KPIs and knowledge gaps for the workspace."""
        workspace = get_object_or_404(Workspace, pk=workspace_id)

        is_privileged = request.user.is_staff or request.user.is_superuser
        has_access = (
            is_privileged
            or workspace.users.filter(pk=request.user.pk).exists()
        )
        if not has_access:
            return Response(
                {'detail': 'Доступ заборонено'},
                status=status.HTTP_403_FORBIDDEN,
            )

        range_param = request.query_params.get('range', '30d')
        data = get_workspace_analytics(workspace, date_range=range_param)
        return Response(data, status=status.HTTP_200_OK)

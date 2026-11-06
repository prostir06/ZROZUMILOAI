"""Workspace analytics API views."""
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chats.analytics_service import (
    build_analytics_csv,
    get_workspace_analytics,
)
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


class WorkspaceAnalyticsExportView(APIView):
    """
    Export workspace analytics data as Cyrillic-compatible CSV.

    Access permitted to superusers, staff, and assigned workspace teachers.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id: int):
        """Return CSV file attachment for workspace analytics."""
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
        if range_param not in ('today', '7d', '30d', 'all'):
            range_param = '30d'
        csv_text = build_analytics_csv(workspace, date_range=range_param)

        slug = (
            getattr(workspace, 'slug', None)
            or slugify(workspace.name)
            or str(workspace.id)
        )
        filename = f'analytics_{slug}_{range_param}.csv'

        response = HttpResponse(
            csv_text,
            content_type='text/csv; charset=utf-8',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

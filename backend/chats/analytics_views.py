"""Workspace analytics API views."""
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chats.analytics_service import (
    build_analytics_csv,
    get_workspace_analytics,
)
from chats.models import WorkspaceChatLog
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
        resolved_param = request.query_params.get('resolved')
        data = get_workspace_analytics(
            workspace,
            date_range=range_param,
            resolved=resolved_param,
        )
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


class WorkspaceKnowledgeGapResolveView(APIView):
    """
    Mark a knowledge gap (workspace chat log) as resolved or unresolved.

    Access permitted to superusers, staff, and assigned workspace teachers.
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request, workspace_id: int, log_id: int):
        """Toggle or set resolved status on the workspace chat log."""
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

        log = get_object_or_404(
            WorkspaceChatLog,
            pk=log_id,
            workspace_id=workspace.pk,
        )

        resolved_val = request.data.get('resolved', True)
        if isinstance(resolved_val, str):
            resolved = resolved_val.strip().lower() in ('true', '1', 'yes')
        else:
            resolved = bool(resolved_val)

        if resolved:
            log.is_resolved = True
            log.resolved_at = timezone.now()
        else:
            log.is_resolved = False
            log.resolved_at = None

        log.save(update_fields=['is_resolved', 'resolved_at'])

        return Response({
            'id': log.id,
            'is_resolved': log.is_resolved,
            'resolved_at': (
                log.resolved_at.isoformat() if log.resolved_at else None
            ),
        }, status=status.HTTP_200_OK)


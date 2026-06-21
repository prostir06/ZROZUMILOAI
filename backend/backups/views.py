"""API views for database backups."""
from django.http import FileResponse
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import BackupService


class BackupListCreateView(APIView):
    """List backups or create a new one."""

    permission_classes = (IsAdminUser,)

    def get(self, request):
        service = BackupService()
        try:
            return Response({'backups': service.list_backups()})
        except RuntimeError as exc:
            return Response(
                {'error': str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        service = BackupService()
        try:
            backup = service.create_backup()
            return Response(backup, status=status.HTTP_201_CREATED)
        except (RuntimeError, FileNotFoundError, OSError, PermissionError) as exc:
            return Response(
                {'error': str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class BackupDownloadView(APIView):
    """Download a backup file."""

    permission_classes = (IsAdminUser,)

    def get(self, request, filename):
        service = BackupService()
        try:
            path = service.get_backup_path(filename)
            return FileResponse(
                path.open('rb'),
                as_attachment=True,
                filename=filename,
            )
        except (ValueError, FileNotFoundError) as exc:
            return Response(
                {'error': str(exc)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except OSError as exc:
            return Response(
                {'error': str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class BackupDeleteView(APIView):
    """Delete a backup file."""

    permission_classes = (IsAdminUser,)

    def delete(self, request, filename):
        service = BackupService()
        try:
            result = service.delete_backup(filename)
            return Response(result)
        except (ValueError, FileNotFoundError) as exc:
            return Response(
                {'error': str(exc)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except OSError as exc:
            return Response(
                {'error': str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

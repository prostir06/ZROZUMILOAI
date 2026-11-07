"""API views for database backups."""
import logging

from django.http import FileResponse
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import BackupService

logger = logging.getLogger(__name__)


class BackupListCreateView(APIView):
    """List backups or create a new one."""

    permission_classes = (IsAdminUser,)

    def get(self, request):
        service = BackupService()
        try:
            return Response({'backups': service.list_backups()})
        except RuntimeError as exc:
            logger.exception('Backup list failed: %s', exc)
            return Response(
                {'error': 'Не вдалося отримати список резервних копій'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        service = BackupService()
        try:
            backup = service.create_backup()
            return Response(backup, status=status.HTTP_201_CREATED)
        except (RuntimeError, FileNotFoundError, OSError, PermissionError) as exc:
            logger.exception('Backup create failed: %s', exc)
            return Response(
                {'error': 'Не вдалося створити резервну копію'},
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
        except ValueError as exc:
            logger.warning(
                'Invalid backup filename or path traversal attempt (%s): %s',
                filename,
                exc,
            )
            return Response(
                {'error': 'Некоректне ім\'я файлу резервної копії'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except FileNotFoundError:
            return Response(
                {'error': 'Файл резервної копії не знайдено'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except OSError as exc:
            logger.exception('Backup download failed: %s', exc)
            return Response(
                {'error': 'Не вдалося завантажити резервну копію'},
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
        except ValueError as exc:
            logger.warning(
                'Invalid backup filename or path traversal attempt (%s): %s',
                filename,
                exc,
            )
            return Response(
                {'error': 'Некоректне ім\'я файлу резервної копії'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except FileNotFoundError:
            return Response(
                {'error': 'Файл резервної копії не знайдено'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except OSError as exc:
            logger.exception('Backup delete failed: %s', exc)
            return Response(
                {'error': 'Не вдалося видалити резервну копію'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

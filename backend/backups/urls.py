"""URL routes for backups."""
from django.urls import path

from .views import BackupDeleteView, BackupDownloadView, BackupListCreateView

urlpatterns = [
    path('', BackupListCreateView.as_view(), name='backup_list_create'),
    path(
        '<str:filename>/download/',
        BackupDownloadView.as_view(),
        name='backup_download',
    ),
    path(
        '<str:filename>/',
        BackupDeleteView.as_view(),
        name='backup_delete',
    ),
]

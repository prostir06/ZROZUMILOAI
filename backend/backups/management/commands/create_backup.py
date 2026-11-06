"""Створити файл резервної копії БД у BACKUP_DIR (для cron / ops)."""
from django.core.management.base import BaseCommand, CommandError

from backups.services import BackupService


class Command(BaseCommand):
    help = 'Створює SQL/SQLite backup у BACKUP_DIR і друкує ім\'я файлу.'

    def handle(self, *args, **options):
        service = BackupService()
        try:
            info = service.create_backup()
        except Exception as exc:
            raise CommandError(f'Backup failed: {exc}') from exc

        filename = info.get('filename', '')
        self.stdout.write(self.style.SUCCESS(filename or str(info)))

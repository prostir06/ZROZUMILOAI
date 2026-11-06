"""Створити файл резервної копії БД у BACKUP_DIR (для cron / ops)."""
from django.core.management.base import BaseCommand, CommandError

from backups.services import BackupService


class Command(BaseCommand):
    help = 'Створює SQL/SQLite backup у BACKUP_DIR і друкує ім\'я файлу.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-media',
            action='store_true',
            help='Створити бекап без вмісту директорії media',
        )

    def handle(self, *args, **options):
        service = BackupService()
        include_media = not options.get('no_media', False)
        try:
            info = service.create_backup(include_media=include_media)
        except Exception as exc:
            raise CommandError(f'Backup failed: {exc}') from exc

        filename = info.get('filename', '')
        has_media = info.get('has_media', False)
        self.stdout.write(
            self.style.SUCCESS(f'{filename} (has_media={has_media})'),
        )

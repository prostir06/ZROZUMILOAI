"""Restore database from backup when FORCE_DB_RESTORE=1."""
import os
import tarfile

from django.core.management.base import BaseCommand

from backups.services import BackupService


class Command(BaseCommand):
    help = (
        'Відновлює БД з файлу в BACKUP_DIR (або найновішого за замовчуванням), '
        'якщо FORCE_DB_RESTORE=1.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'filename',
            nargs='?',
            default=None,
            help="Ім'я файлу бекапу (якщо не вказано — найновіший)",
        )

    def handle(self, *args, **options):
        force_restore = os.getenv('FORCE_DB_RESTORE', '0').lower()
        if force_restore not in ('1', 'true', 'yes'):
            self.stdout.write('FORCE_DB_RESTORE вимкнено — пропуск.')
            return

        service = BackupService()
        filename = options.get('filename')

        if filename:
            target_name = filename
        else:
            backup_path = service.find_latest_backup()
            if backup_path is None:
                self.stdout.write(
                    self.style.WARNING(
                        f'У теці {service.backup_dir} немає файлів backup.',
                    ),
                )
                return
            target_name = backup_path.name

        self.stdout.write(
            f'Відновлення з файлу: {target_name}',
        )

        try:
            if filename:
                restored = service.restore_backup(filename)
            else:
                restored = service.restore_latest_backup()
        except (RuntimeError, FileNotFoundError, ValueError, tarfile.TarError, OSError) as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            raise SystemExit(1) from exc

        if restored:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Базу даних відновлено з "{restored["filename"]}".',
                ),
            )

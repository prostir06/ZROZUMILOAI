"""Restore database from the latest backup when FORCE_DB_RESTORE=1."""
import os

from django.core.management.base import BaseCommand

from backups.services import BackupService


class Command(BaseCommand):
    help = (
        'Відновлює БД з найновішого файлу в BACKUP_DIR, '
        'якщо FORCE_DB_RESTORE=1.'
    )

    def handle(self, *args, **options):
        force_restore = os.getenv('FORCE_DB_RESTORE', '0').lower()
        if force_restore not in ('1', 'true', 'yes'):
            self.stdout.write('FORCE_DB_RESTORE вимкнено — пропуск.')
            return

        service = BackupService()
        backup_path = service.find_latest_backup()

        if backup_path is None:
            self.stdout.write(
                self.style.WARNING(
                    f'У теці {service.backup_dir} немає файлів backup.',
                ),
            )
            return

        self.stdout.write(
            f'Відновлення з файлу: {backup_path.name}',
        )

        try:
            restored = service.restore_latest_backup()
        except (RuntimeError, FileNotFoundError) as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            raise SystemExit(1) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f'Базу даних відновлено з "{restored["filename"]}".',
            ),
        )

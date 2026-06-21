"""Unit-тести для BackupService."""
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings

from backups.services import BackupService


class BackupServiceTests(TestCase):
    """Тести сервісу резервного копіювання."""

    def setUp(self):
        """Тимчасовий каталог для backup-файлів."""
        self.temp_dir = tempfile.mkdtemp()
        self.service = BackupService(backup_dir=self.temp_dir)

    def tearDown(self):
        """Видалення тимчасового каталогу після тестів."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_resolve_safe_path_rejects_traversal(self):
        """Path traversal у імені файлу блокується."""
        with self.assertRaises(ValueError):
            self.service._resolve_safe_path('../etc/passwd.sql')

    def test_resolve_safe_path_rejects_wrong_extension(self):
        """Дозволені лише певні розширення backup-файлів."""
        with self.assertRaises(ValueError):
            self.service._resolve_safe_path('evil.exe')

    @override_settings(
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.mysql',
                'NAME': 'test',
            },
        },
    )
    def test_create_backup_unsupported_engine(self):
        """Непідтримуваний тип БД викликає RuntimeError."""
        with self.assertRaises(RuntimeError):
            self.service.create_backup()

    def test_list_backups_empty_directory(self):
        """Порожній каталог повертає порожній список."""
        self.assertEqual(self.service.list_backups(), [])

    def test_get_backup_path_not_found(self):
        """Відсутній файл викликає FileNotFoundError."""
        Path(self.temp_dir, 'backup_test_20240101_120000.sql').touch()
        with self.assertRaises(FileNotFoundError):
            self.service.get_backup_path('missing.sql')

    def test_list_backups_handles_os_error(self):
        """Помилка читання каталогу обгортається в RuntimeError."""
        with patch.object(Path, 'iterdir', side_effect=OSError('denied')):
            with self.assertRaises(RuntimeError):
                self.service.list_backups()

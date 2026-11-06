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

    def test_quote_pg_ident_allows_safe_names(self):
        """Звичайні імена ролей PostgreSQL екрануються в лапки."""
        self.assertEqual(self.service._quote_pg_ident('zrozumiloai'), '"zrozumiloai"')

    def test_quote_pg_ident_rejects_injection(self):
        """Метасимволи / shell-injection у імені ролі відхиляються."""
        for bad in ('admin; \\! rm', 'a b', 'x-y', '"evil"', ''):
            with self.assertRaises(ValueError):
                self.service._quote_pg_ident(bad)

    @override_settings(
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': 'test',
                'USER': 'safe_user',
            },
        },
    )
    def test_restore_postgresql_uses_transactional_script(self):
        """Restore пише BEGIN/COMMIT і не DROP-ає окремо до restore."""
        dump = Path(self.temp_dir) / 'dump.sql'
        dump.write_text('-- dump\n', encoding='utf-8')
        with patch.object(self.service, '_run_psql') as mock_psql:
            self.service._restore_postgresql(dump)
        mock_psql.assert_called_once()
        args = mock_psql.call_args.args
        self.assertIn('-f', args)
        script_path = Path(args[args.index('-f') + 1])
        self.assertFalse(script_path.exists())
        # Скрипт видаляється в finally; перевіряємо виклик із ON_ERROR_STOP.
        self.assertEqual(args[0], '-v')
        self.assertEqual(args[1], 'ON_ERROR_STOP=1')

    def test_create_backup_includes_media_when_requested(self):
        tmp_path = Path(self.temp_dir)
        media_dir = tmp_path / 'media' / 'workspace_documents' / '1'
        media_dir.mkdir(parents=True)
        sample_file = media_dir / 'test.pdf'
        sample_file.write_bytes(b'%PDF-1.4 sample content')

        backup_dir = tmp_path / 'backups'
        service = BackupService(backup_dir=backup_dir)

        with override_settings(MEDIA_ROOT=str(tmp_path / 'media')):
            info = service.create_backup(include_media=True)
            self.assertTrue(info['filename'].endswith('.tar.gz'))
            self.assertTrue((backup_dir / info['filename']).exists())
            self.assertIs(info.get('has_media'), True)

    def test_create_backup_without_media_creates_raw_dump(self):
        """include_media=False створює стандартний сирий файл (.sql/.sqlite3)."""
        backup_dir = Path(self.temp_dir) / 'backups'
        service = BackupService(backup_dir=backup_dir)
        info = service.create_backup(include_media=False)
        self.assertFalse(info['filename'].endswith('.tar.gz'))
        self.assertTrue(info['filename'].endswith(('.sql', '.sqlite3', '.db')))
        self.assertTrue((backup_dir / info['filename']).exists())
        self.assertIs(info.get('has_media'), False)

    def test_archive_bundle_contains_valid_manifest_and_structure(self):
        """Архів .tar.gz містить manifest.json, dump-файл та media-файли."""
        import json
        import tarfile

        tmp_path = Path(self.temp_dir)
        doc_path = tmp_path / 'media' / 'workspace_documents' / '2' / 'doc.txt'
        doc_path.parent.mkdir(parents=True)
        doc_path.write_text('document text', encoding='utf-8')

        backup_dir = tmp_path / 'backups'
        service = BackupService(backup_dir=backup_dir)

        with override_settings(MEDIA_ROOT=str(tmp_path / 'media')):
            info = service.create_backup(include_media=True)
            archive_path = backup_dir / info['filename']
            self.assertTrue(archive_path.exists())

            with tarfile.open(archive_path, 'r:gz') as tar:
                names = tar.getnames()
                self.assertIn('manifest.json', names)
                # Чи є dump.sql або dump.sqlite3
                has_dump = any(name in ('dump.sql', 'dump.sqlite3') for name in names)
                self.assertTrue(has_dump)
                # Чи є файл медіа
                media_member = 'media/workspace_documents/2/doc.txt'
                self.assertIn(media_member, names)

                manifest_file = tar.extractfile('manifest.json')
                self.assertIsNotNone(manifest_file)
                manifest_data = json.load(manifest_file)
                self.assertEqual(manifest_data['version'], '1.0')
                self.assertEqual(manifest_data['format'], 'tar.gz')
                self.assertTrue(manifest_data['has_media'])
                self.assertIn('dump_file', manifest_data)
                self.assertIn('files', manifest_data)

    def test_create_backup_when_workspace_documents_missing(self):
        """Якщо каталог workspace_documents відсутній, has_media дорівнює False."""
        tmp_path = Path(self.temp_dir)
        media_dir = tmp_path / 'media_empty'
        media_dir.mkdir(parents=True)

        backup_dir = tmp_path / 'backups'
        service = BackupService(backup_dir=backup_dir)

        with override_settings(MEDIA_ROOT=str(media_dir)):
            info = service.create_backup(include_media=True)
            self.assertTrue(info['filename'].endswith('.tar.gz'))
            self.assertIs(info.get('has_media'), False)

    @override_settings(
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': 'test_pg_db',
                'USER': 'pg_user',
                'PASSWORD': 'secret',
                'HOST': 'localhost',
                'PORT': '5432',
            },
        },
    )
    def test_create_backup_postgresql_archive(self):
        """PostgreSQL бекап створює dump.sql та пакує в .tar.gz."""
        import tarfile
        tmp_path = Path(self.temp_dir)
        backup_dir = tmp_path / 'backups'
        service = BackupService(backup_dir=backup_dir)

        def fake_pg_dump(cmd, **kwargs):
            # Знаходимо -f аргумент і пишемо фіктивний дамп
            out_idx = cmd.index('-f') + 1
            out_file = Path(cmd[out_idx])
            out_file.write_text('-- PG DUMP TEST CONTENT --', encoding='utf-8')
            class FakeResult:
                returncode = 0
                stderr = ''
            return FakeResult()

        with patch('subprocess.run', side_effect=fake_pg_dump):
            info = service.create_backup(include_media=False)
            self.assertTrue(info['filename'].endswith('.sql'))
            self.assertIs(info.get('has_media'), False)

            info_archive = service.create_backup(include_media=True)
            self.assertTrue(info_archive['filename'].endswith('.tar.gz'))
            archive_path = backup_dir / info_archive['filename']
            with tarfile.open(archive_path, 'r:gz') as tar:
                names = tar.getnames()
                self.assertIn('dump.sql', names)
                self.assertIn('manifest.json', names)

    def test_list_backups_includes_tar_gz(self):
        """list_backups розпізнає та повертає .tar.gz архіви з полем has_media."""
        tmp_path = Path(self.temp_dir)
        backup_dir = tmp_path / 'backups'
        service = BackupService(backup_dir=backup_dir)
        info = service.create_backup(include_media=True)

        backups = service.list_backups()
        filenames = [b['filename'] for b in backups]
        self.assertIn(info['filename'], filenames)
        backup_entry = next(b for b in backups if b['filename'] == info['filename'])
        self.assertIn('has_media', backup_entry)

    def test_get_backup_path_tar_gz(self):
        """get_backup_path валідує і повертає шлях до .tar.gz архіву."""
        tmp_path = Path(self.temp_dir)
        backup_dir = tmp_path / 'backups'
        service = BackupService(backup_dir=backup_dir)
        info = service.create_backup(include_media=True)

        path = service.get_backup_path(info['filename'])
        self.assertTrue(path.exists())
        self.assertEqual(path.name, info['filename'])





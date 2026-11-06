"""Unit tests for backup management commands."""
import io
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from backups.services import BackupService


class BackupCommandsTests(TestCase):
    """Test create_backup and restore_backup management commands."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.backup_dir = Path(self.temp_dir) / 'backup'
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir = Path(self.temp_dir) / 'media'
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self.test_db = Path(self.temp_dir) / 'test_app.sqlite3'
        self.test_db.write_bytes(b'sqlite format 3\x00')

        # Create workspace_documents for media backups
        ws_docs = self.media_dir / 'workspace_documents' / '1'
        ws_docs.mkdir(parents=True, exist_ok=True)
        (ws_docs / 'doc.txt').write_text('document content', encoding='utf-8')

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_backup_produces_backup_and_outputs_filename(self):
        """create_backup creates a bundle backup and prints filename to stdout."""
        out = io.StringIO()
        with override_settings(
            BACKUP_DIR=str(self.backup_dir),
            MEDIA_ROOT=str(self.media_dir),
            DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(self.test_db)}},
        ):
            call_command('create_backup', stdout=out)

        output = out.getvalue()
        service = BackupService(backup_dir=self.backup_dir)
        backups = service.list_backups()
        self.assertEqual(len(backups), 1)
        latest = backups[0]
        self.assertTrue(latest['filename'].endswith('.tar.gz'))
        self.assertTrue(latest['has_media'])
        self.assertIn(latest['filename'], output)
        self.assertIn('has_media=True', output)

    def test_create_backup_no_media_creates_backup_with_has_media_false(self):
        """create_backup --no-media produces raw dump without media."""
        out = io.StringIO()
        with override_settings(
            BACKUP_DIR=str(self.backup_dir),
            MEDIA_ROOT=str(self.media_dir),
            DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(self.test_db)}},
        ):
            call_command('create_backup', '--no-media', stdout=out)

        output = out.getvalue()
        service = BackupService(backup_dir=self.backup_dir)
        backups = service.list_backups()
        self.assertEqual(len(backups), 1)
        latest = backups[0]
        self.assertTrue(latest['filename'].endswith('.sqlite3'))
        self.assertFalse(latest['has_media'])
        self.assertIn(latest['filename'], output)
        self.assertIn('has_media=False', output)

    def test_restore_backup_skips_when_force_restore_not_set(self):
        """restore_backup skips if FORCE_DB_RESTORE is not set."""
        out = io.StringIO()
        with patch.dict(os.environ, {'FORCE_DB_RESTORE': '0'}, clear=False):
            with override_settings(BACKUP_DIR=str(self.backup_dir)):
                call_command('restore_backup', stdout=out)

        output = out.getvalue()
        self.assertIn('FORCE_DB_RESTORE вимкнено — пропуск.', output)

    def test_restore_backup_restores_latest_backup_when_force_restore_enabled(self):
        """restore_backup restores the latest backup when FORCE_DB_RESTORE=1."""
        target_db = Path(self.temp_dir) / 'target.sqlite3'
        target_db.write_bytes(b'initial target db')

        backup1 = self.backup_dir / 'backup_default_20260101_100000_000000.sqlite3'
        backup1.write_bytes(b'backup 1 content')
        os.utime(backup1, (1000000000, 1000000000))

        backup2 = self.backup_dir / 'backup_default_20260102_100000_000000.sqlite3'
        backup2.write_bytes(b'backup 2 content')
        os.utime(backup2, (2000000000, 2000000000))

        out = io.StringIO()
        with patch.dict(os.environ, {'FORCE_DB_RESTORE': '1'}, clear=False):
            with override_settings(
                BACKUP_DIR=str(self.backup_dir),
                DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(target_db)}},
            ):
                call_command('restore_backup', stdout=out)

        output = out.getvalue()
        self.assertIn(f'Відновлення з файлу: {backup2.name}', output)
        self.assertIn(f'Базу даних відновлено з "{backup2.name}".', output)
        self.assertEqual(target_db.read_bytes(), b'backup 2 content')

    def test_restore_backup_specific_filename_when_force_restore_enabled(self):
        """restore_backup <filename> restores specific backup file."""
        target_db = Path(self.temp_dir) / 'target.sqlite3'
        target_db.write_bytes(b'initial target db')

        backup1 = self.backup_dir / 'backup_default_20260101_100000_000000.sqlite3'
        backup1.write_bytes(b'backup 1 content')
        os.utime(backup1, (1000000000, 1000000000))

        backup2 = self.backup_dir / 'backup_default_20260102_100000_000000.sqlite3'
        backup2.write_bytes(b'backup 2 content')
        os.utime(backup2, (2000000000, 2000000000))

        out = io.StringIO()
        with patch.dict(os.environ, {'FORCE_DB_RESTORE': '1'}, clear=False):
            with override_settings(
                BACKUP_DIR=str(self.backup_dir),
                DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(target_db)}},
            ):
                call_command('restore_backup', backup1.name, stdout=out)

        output = out.getvalue()
        self.assertIn(f'Відновлення з файлу: {backup1.name}', output)
        self.assertIn(f'Базу даних відновлено з "{backup1.name}".', output)
        self.assertEqual(target_db.read_bytes(), b'backup 1 content')

    def test_restore_backup_empty_dir_when_force_restore_enabled(self):
        """restore_backup outputs warning if no backups exist."""
        out = io.StringIO()
        with patch.dict(os.environ, {'FORCE_DB_RESTORE': '1'}, clear=False):
            with override_settings(
                BACKUP_DIR=str(self.backup_dir),
                DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(self.test_db)}},
            ):
                call_command('restore_backup', stdout=out)

        output = out.getvalue()
        self.assertIn('немає файлів backup', output)

    def test_restore_backup_missing_file_raises_system_exit(self):
        """restore_backup <nonexistent> exits with error."""
        out = io.StringIO()
        err = io.StringIO()
        with patch.dict(os.environ, {'FORCE_DB_RESTORE': '1'}, clear=False):
            with override_settings(
                BACKUP_DIR=str(self.backup_dir),
                DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(self.test_db)}},
            ):
                with self.assertRaises(SystemExit):
                    call_command('restore_backup', 'nonexistent.sqlite3', stdout=out, stderr=err)

    def test_restore_backup_corrupted_tar_file_raises_system_exit(self):
        """restore_backup <corrupted.tar.gz> exits cleanly with SystemExit(1)."""
        corrupted = self.backup_dir / 'backup_corrupted_20260101_100000_000000.tar.gz'
        corrupted.write_bytes(b'not a valid tar file content')

        out = io.StringIO()
        err = io.StringIO()
        with patch.dict(os.environ, {'FORCE_DB_RESTORE': '1'}, clear=False):
            with override_settings(
                BACKUP_DIR=str(self.backup_dir),
                DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(self.test_db)}},
            ):
                with self.assertRaises(SystemExit) as ctx:
                    call_command('restore_backup', corrupted.name, stdout=out, stderr=err)
                self.assertEqual(ctx.exception.code, 1)
        self.assertTrue(len(err.getvalue()) > 0)

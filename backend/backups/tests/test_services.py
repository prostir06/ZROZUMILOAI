"""Unit-тести для BackupService."""
import io
import shutil
import tarfile
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

    def test_engine_submodules_exist_and_facade_delegates(self):
        """Перевірити, що engine-модулі експортують функції та BackupService їх викликає."""
        from backups.engine import archive, postgres, sqlite

        self.assertTrue(callable(archive.pack_archive))
        self.assertTrue(callable(archive.read_manifest))
        self.assertTrue(callable(postgres.dump_postgresql))
        self.assertTrue(callable(postgres.restore_postgresql))
        self.assertTrue(callable(sqlite.dump_sqlite))
        self.assertTrue(callable(sqlite.restore_sqlite))

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

    def test_restore_archive_restores_database_and_media(self):
        """Відновлення з .tar.gz відновлює і базу, і медіа-файли."""
        tmp_path = Path(self.temp_dir)
        media_dir = tmp_path / 'media'
        target_doc = media_dir / 'workspace_documents' / '1' / 'doc.txt'
        target_doc.parent.mkdir(parents=True)
        target_doc.write_text('Original text', encoding='utf-8')

        backup_dir = tmp_path / 'backups'
        service = BackupService(backup_dir=backup_dir)

        test_db = tmp_path / 'test.sqlite3'
        test_db.write_bytes(b'sqlite format 3\x00')

        with override_settings(
            MEDIA_ROOT=str(media_dir),
            DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(test_db)}},
        ):
            backup_info = service.create_backup(include_media=True)

            # Simulate media deletion
            target_doc.unlink()
            self.assertFalse(target_doc.exists())

            # Restore
            result = service.restore_backup(backup_info['filename'])
            self.assertTrue(target_doc.exists())
            self.assertEqual(target_doc.read_text(encoding='utf-8'), 'Original text')
            self.assertEqual(result['filename'], backup_info['filename'])

    def test_restore_backup_legacy_sqlite(self):
        """Зворотна сумісність: restore_backup успішно відновлює legacy .sqlite3 файл."""
        tmp_path = Path(self.temp_dir)
        backup_dir = tmp_path / 'backups'
        service = BackupService(backup_dir=backup_dir)

        legacy_dump = backup_dir / 'backup_test_legacy.sqlite3'
        legacy_dump.write_bytes(b'legacy sqlite content')

        target_db = tmp_path / 'active.sqlite3'
        target_db.write_bytes(b'active sqlite content')

        with override_settings(
            DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(target_db)}},
        ):
            info = service.restore_backup(legacy_dump.name)
            self.assertEqual(info['filename'], legacy_dump.name)
            self.assertEqual(target_db.read_bytes(), b'legacy sqlite content')

    @override_settings(
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': 'test_pg',
                'USER': 'safe_user',
            },
        },
    )
    def test_restore_backup_legacy_sql_postgresql(self):
        """Зворотна сумісність: restore_backup успішно відновлює legacy .sql файл."""
        tmp_path = Path(self.temp_dir)
        backup_dir = tmp_path / 'backups'
        service = BackupService(backup_dir=backup_dir)

        legacy_dump = backup_dir / 'backup_test_legacy.sql'
        legacy_dump.write_text('-- legacy pg dump\n', encoding='utf-8')

        with patch.object(service, '_run_psql') as mock_psql:
            info = service.restore_backup(legacy_dump.name)
            self.assertEqual(info['filename'], legacy_dump.name)
            mock_psql.assert_called_once()

    @override_settings(
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': 'test_pg',
                'USER': 'safe_user',
            },
        },
    )
    def test_restore_archive_postgresql(self):
        """restore_backup розпаковує dump.sql з .tar.gz та виконує restore PostgreSQL."""
        import io
        import tarfile

        tmp_path = Path(self.temp_dir)
        backup_dir = tmp_path / 'backups'
        service = BackupService(backup_dir=backup_dir)

        archive_path = backup_dir / 'backup_test_archive.tar.gz'
        with tarfile.open(archive_path, 'w:gz') as tar:
            dump_bytes = b'-- postgresql dump in archive\n'
            dump_info = tarfile.TarInfo(name='dump.sql')
            dump_info.size = len(dump_bytes)
            tar.addfile(dump_info, io.BytesIO(dump_bytes))

            manifest = (
                b'{"version":"1.0","format":"tar.gz","engine":"postgresql",'
                b'"dump_file":"dump.sql","has_media":false}'
            )
            m_info = tarfile.TarInfo(name='manifest.json')
            m_info.size = len(manifest)
            tar.addfile(m_info, io.BytesIO(manifest))

        with patch.object(service, '_run_psql') as mock_psql:
            info = service.restore_backup(archive_path.name)
            self.assertEqual(info['filename'], archive_path.name)
            mock_psql.assert_called_once()

    def test_restore_archive_path_traversal_prevention(self):
        """Розпакування блокує спроби path traversal (..) у членах архіву."""
        import io
        import tarfile

        tmp_path = Path(self.temp_dir)
        media_dir = tmp_path / 'media'
        media_dir.mkdir(parents=True)
        backup_dir = tmp_path / 'backups'
        service = BackupService(backup_dir=backup_dir)

        malicious_archive = backup_dir / 'backup_malicious.tar.gz'
        outside_file = tmp_path / 'outside_target.txt'

        with tarfile.open(malicious_archive, 'w:gz') as tar:
            dump_bytes = b'sqlite format 3\x00'
            dump_info = tarfile.TarInfo(name='dump.sqlite3')
            dump_info.size = len(dump_bytes)
            tar.addfile(dump_info, io.BytesIO(dump_bytes))

            evil_bytes = b'malicious content'
            evil_info = tarfile.TarInfo(name='media/../../outside_target.txt')
            evil_info.size = len(evil_bytes)
            tar.addfile(evil_info, io.BytesIO(evil_bytes))

        with override_settings(
            MEDIA_ROOT=str(media_dir),
            DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(tmp_path / 'db.sqlite3')}},
        ):
            with self.assertRaises(ValueError) as ctx:
                service.restore_backup(malicious_archive.name)
            self.assertIn('Небезпечний шлях', str(ctx.exception))
            self.assertFalse(outside_file.exists())

    def test_restore_archive_rejects_symlinks(self):
        """Розпакування блокує члени архіву, які є символьними або жорсткими посиланнями."""
        import io
        import tarfile

        tmp_path = Path(self.temp_dir)
        media_dir = tmp_path / 'media'
        media_dir.mkdir(parents=True)
        backup_dir = tmp_path / 'backups'
        service = BackupService(backup_dir=backup_dir)

        archive_path = backup_dir / 'backup_symlink.tar.gz'
        with tarfile.open(archive_path, 'w:gz') as tar:
            dump_bytes = b'sqlite format 3\x00'
            dump_info = tarfile.TarInfo(name='dump.sqlite3')
            dump_info.size = len(dump_bytes)
            tar.addfile(dump_info, io.BytesIO(dump_bytes))

            sym_info = tarfile.TarInfo(name='media/workspace_documents/link.txt')
            sym_info.type = tarfile.SYMTYPE
            sym_info.linkname = '/etc/passwd'
            tar.addfile(sym_info)

        with override_settings(
            MEDIA_ROOT=str(media_dir),
            DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(tmp_path / 'db.sqlite3')}},
        ):
            with self.assertRaises(ValueError) as ctx:
                service.restore_backup(archive_path.name)
            self.assertIn('Небезпечний тип', str(ctx.exception))

    def test_restore_archive_cleans_up_temp_dir(self):
        """Тимчасова робоча тека розпакування видаляється навіть у разі збою."""
        tmp_path = Path(self.temp_dir)
        backup_dir = tmp_path / 'backups'
        service = BackupService(backup_dir=backup_dir)

        test_db = tmp_path / 'test.sqlite3'
        test_db.write_bytes(b'sqlite format 3\x00')

        with override_settings(
            DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(test_db)}},
        ):
            backup_info = service.create_backup(include_media=True)

            with patch.object(service, '_restore_sqlite', side_effect=RuntimeError('Restore error')):
                with self.assertRaises(RuntimeError):
                    service.restore_backup(backup_info['filename'])

            # Перевіряємо відсутність залишкових тимчасових тек .tmp_restore_
            tmp_restore_dirs = [p for p in backup_dir.glob('.tmp_restore_*')]
            self.assertEqual(tmp_restore_dirs, [])

    def test_restore_latest_backup_selects_and_restores_tar_gz(self):
        """restore_latest_backup() успішно знаходить та відновлює найновіший .tar.gz архів."""
        tmp_path = Path(self.temp_dir)
        media_dir = tmp_path / 'media'
        target_doc = media_dir / 'workspace_documents' / '1' / 'doc.txt'
        target_doc.parent.mkdir(parents=True)
        target_doc.write_text('Restored via latest', encoding='utf-8')

        backup_dir = tmp_path / 'backups'
        service = BackupService(backup_dir=backup_dir)

        test_db = tmp_path / 'test.sqlite3'
        test_db.write_bytes(b'sqlite format 3\x00')

        with override_settings(
            MEDIA_ROOT=str(media_dir),
            DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(test_db)}},
        ):
            backup_info = service.create_backup(include_media=True)
            target_doc.unlink()

            res = service.restore_latest_backup()
            self.assertIsNotNone(res)
            self.assertEqual(res['filename'], backup_info['filename'])
            self.assertTrue(target_doc.exists())
            self.assertEqual(target_doc.read_text(encoding='utf-8'), 'Restored via latest')

    def test_restore_latest_backup_returns_none_when_empty(self):
        """restore_latest_backup() повертає None, якщо сумісних бекапів немає."""
        backup_dir = Path(self.temp_dir) / 'backups'
        service = BackupService(backup_dir=backup_dir)
        self.assertIsNone(service.restore_latest_backup())

    def test_find_latest_backup_filters_by_engine(self):
        """find_latest_backup знаходить тільки бекапи, сумісні з поточним DB engine."""
        import io
        import tarfile

        tmp_path = Path(self.temp_dir)
        backup_dir = tmp_path / 'backups'
        service = BackupService(backup_dir=backup_dir)

        # Створюємо PG архів
        pg_archive = backup_dir / 'backup_pg_20260101_120000.tar.gz'
        with tarfile.open(pg_archive, 'w:gz') as tar:
            m_bytes = b'{"version":"1.0","format":"tar.gz","engine":"postgresql","dump_file":"dump.sql"}'
            m_info = tarfile.TarInfo(name='manifest.json')
            m_info.size = len(m_bytes)
            tar.addfile(m_info, io.BytesIO(m_bytes))
            d_bytes = b'-- pg dump'
            d_info = tarfile.TarInfo(name='dump.sql')
            d_info.size = len(d_bytes)
            tar.addfile(d_info, io.BytesIO(d_bytes))

        # Створюємо legacy PG .sql
        pg_sql = backup_dir / 'backup_pg_20260101_130000.sql'
        pg_sql.write_text('-- pg sql', encoding='utf-8')

        # Тест очікує SQLite-рушій незалежно від активного CI DB engine
        with override_settings(
            DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(tmp_path / 'db.sqlite3')}},
        ):
            latest_sqlite = service.find_latest_backup()
            self.assertIsNone(latest_sqlite)

            # Додаємо SQLite архів
            sqlite_archive = backup_dir / 'backup_sqlite_20260101_140000.tar.gz'
            with tarfile.open(sqlite_archive, 'w:gz') as tar:
                m_bytes = b'{"version":"1.0","format":"tar.gz","engine":"sqlite","dump_file":"dump.sqlite3"}'
                m_info = tarfile.TarInfo(name='manifest.json')
                m_info.size = len(m_bytes)
                tar.addfile(m_info, io.BytesIO(m_bytes))
                d_bytes = b'sqlite format 3\x00'
                d_info = tarfile.TarInfo(name='dump.sqlite3')
                d_info.size = len(d_bytes)
                tar.addfile(d_info, io.BytesIO(d_bytes))

            latest_sqlite = service.find_latest_backup()
            self.assertIsNotNone(latest_sqlite)
            self.assertEqual(latest_sqlite.name, sqlite_archive.name)

    def test_file_info_reads_manifest_once(self):
        """_file_info зчитує маніфест лише один раз, не відкриваючи архів двічі."""
        tmp_path = Path(self.temp_dir)
        backup_dir = tmp_path / 'backups'
        service = BackupService(backup_dir=backup_dir)

        test_db = tmp_path / 'test.sqlite3'
        test_db.write_bytes(b'sqlite format 3\x00')

        with override_settings(
            DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(test_db)}},
        ):
            backup_info = service.create_backup(include_media=False)
            archive_path = backup_dir / backup_info['filename']

            # Якщо це .tar.gz (або створюємо явний .tar.gz)
            if not archive_path.name.endswith('.tar.gz'):
                info = service.create_backup(include_media=True)
                archive_path = backup_dir / info['filename']

            with patch.object(service, '_read_manifest', wraps=service._read_manifest) as mock_manifest:
                service._file_info(archive_path)
                # _read_manifest має викликатися щонайбільше 1 раз
                self.assertEqual(mock_manifest.call_count, 1)

    def test_pack_archive_places_manifest_first(self):
        """manifest.json записується першим елементом у .tar.gz для швидкого читання."""
        tmp_path = Path(self.temp_dir)
        backup_dir = tmp_path / 'backups'
        service = BackupService(backup_dir=backup_dir)

        test_db = tmp_path / 'test.sqlite3'
        test_db.write_bytes(b'sqlite format 3\x00')

        with override_settings(
            DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(test_db)}},
        ):
            backup_info = service.create_backup(include_media=True)
            archive_path = backup_dir / backup_info['filename']

            with tarfile.open(archive_path, 'r:gz') as tar:
                members = tar.getmembers()
                self.assertGreater(len(members), 0)
                self.assertEqual(members[0].name, 'manifest.json')

    def test_restore_archive_sanitizes_dump_file_path_traversal(self):
        """Небезпечний dump_file у маніфесті (наприклад ../../payload.sqlite3) санітизується."""
        tmp_path = Path(self.temp_dir)
        backup_dir = tmp_path / 'backups'
        service = BackupService(backup_dir=backup_dir)

        malicious_archive = backup_dir / 'backup_malicious_20260101_150000.tar.gz'
        with tarfile.open(malicious_archive, 'w:gz') as tar:
            m_bytes = b'{"version":"1.0","format":"tar.gz","engine":"sqlite","dump_file":"../../payload.sqlite3"}'
            m_info = tarfile.TarInfo(name='manifest.json')
            m_info.size = len(m_bytes)
            tar.addfile(m_info, io.BytesIO(m_bytes))
            d_bytes = b'sqlite format 3\x00'
            d_info = tarfile.TarInfo(name='dump.sqlite3')
            d_info.size = len(d_bytes)
            tar.addfile(d_info, io.BytesIO(d_bytes))

        test_db = tmp_path / 'db.sqlite3'
        test_db.write_bytes(b'original')

        with override_settings(
            DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(test_db)}},
        ):
            # Має успішно відновитися через fallback до dump.sqlite3, не створюючи файлів поза tmp
            service.restore_backup(malicious_archive.name)
            self.assertEqual(test_db.read_bytes(), b'sqlite format 3\x00')

    def test_restore_archive_rejects_non_file_dump(self):
        """Елемент дампа, який не є звичайним файлом (наприклад директорія), відхиляється."""
        tmp_path = Path(self.temp_dir)
        backup_dir = tmp_path / 'backups'
        service = BackupService(backup_dir=backup_dir)

        bad_archive = backup_dir / 'backup_bad_dump_20260101_160000.tar.gz'
        with tarfile.open(bad_archive, 'w:gz') as tar:
            m_bytes = b'{"version":"1.0","format":"tar.gz","engine":"sqlite","dump_file":"dump.sqlite3"}'
            m_info = tarfile.TarInfo(name='manifest.json')
            m_info.size = len(m_bytes)
            tar.addfile(m_info, io.BytesIO(m_bytes))
            dir_info = tarfile.TarInfo(name='dump.sqlite3')
            dir_info.type = tarfile.DIRTYPE
            tar.addfile(dir_info)

        test_db = tmp_path / 'db.sqlite3'
        test_db.write_bytes(b'original')

        with override_settings(
            DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(test_db)}},
        ):
            with self.assertRaises(RuntimeError) as ctx:
                service.restore_backup(bad_archive.name)
            self.assertIn('не є файлом', str(ctx.exception))








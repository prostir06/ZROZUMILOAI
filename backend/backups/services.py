"""Database backup service."""
import io
import json
import logging
import os
import re
import shutil
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db import connection

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'.sql', '.sqlite3', '.db', '.tar.gz'}
_PG_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


class BackupService:
    """Create and manage database backup files."""

    def __init__(self, backup_dir=None):
        self.backup_dir = Path(backup_dir or settings.BACKUP_DIR)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _timestamp_name(self, extension):
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        db_name = settings.DATABASES['default'].get('NAME', 'database')
        if isinstance(db_name, Path):
            db_name = db_name.stem
        db_name = re.sub(r'[^A-Za-z0-9_]', '_', str(db_name)).strip('_') or 'database'
        return f'backup_{db_name}_{stamp}{extension}'

    def _resolve_safe_path(self, filename):
        path = (self.backup_dir / filename).resolve()
        backup_dir = self.backup_dir.resolve()
        if not (path == backup_dir or backup_dir in path.parents):
            raise ValueError('Недопустиме ім\'я файлу')
        if not any(path.name.endswith(ext) for ext in ALLOWED_EXTENSIONS):
            raise ValueError('Недопустимий тип файлу')
        return path

    def create_backup(self, include_media=True):
        """Create a new database backup and return metadata."""
        engine = settings.DATABASES['default']['ENGINE']

        if 'postgresql' not in engine and 'sqlite' not in engine:
            raise RuntimeError(f'Непідтримуваний тип БД: {engine}')

        if not include_media:
            if 'postgresql' in engine:
                return self._backup_postgresql()
            if 'sqlite' in engine:
                return self._backup_sqlite()

        is_pg = 'postgresql' in engine
        raw_ext = '.sql' if is_pg else '.sqlite3'
        dump_arcname = 'dump.sql' if is_pg else 'dump.sqlite3'

        temp_dump = self.backup_dir / f'.tmp_dump_{datetime.now().strftime("%Y%m%d%H%M%S%f")}{raw_ext}'
        try:
            if is_pg:
                self._dump_postgresql(temp_dump)
            else:
                self._dump_sqlite(temp_dump)

            return self._pack_archive(temp_dump, dump_arcname, include_media=include_media)
        finally:
            if temp_dump.exists():
                try:
                    temp_dump.unlink()
                except OSError:
                    pass

    def _dump_postgresql(self, target_filepath):
        db = settings.DATABASES['default']
        env = os.environ.copy()
        env['PGPASSWORD'] = db.get('PASSWORD', '')

        command = [
            'pg_dump',
            '-h', db.get('HOST', 'localhost'),
            '-p', str(db.get('PORT', '5432')),
            '-U', db.get('USER', ''),
            '-d', db.get('NAME', ''),
            '-f', str(target_filepath),
            '--clean',
            '--if-exists',
            '--no-owner',
            '--no-acl',
        ]

        try:
            result = subprocess.run(
                command,
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=300,
            )
        except subprocess.TimeoutExpired as exc:
            logger.error('pg_dump timed out after 300s')
            raise RuntimeError('pg_dump перевищив ліміт часу') from exc

        if result.returncode != 0:
            logger.error(
                'pg_dump failed (rc=%s): %s',
                result.returncode,
                (result.stderr or '')[:500],
            )
            raise RuntimeError('pg_dump завершився з помилкою')

    def _dump_sqlite(self, target_filepath):
        db_name = settings.DATABASES['default']['NAME']
        db_path = Path(db_name) if isinstance(db_name, (str, Path)) else None
        if db_path and db_path.exists():
            shutil.copy2(db_path, target_filepath)
            return

        try:
            import sqlite3
            if connection.connection is None:
                connection.connect()
            dest = sqlite3.connect(str(target_filepath))
            try:
                connection.connection.backup(dest)
            finally:
                dest.close()
            return
        except Exception as exc:
            logger.error('SQLite dump failed: %s', exc)

        raise FileNotFoundError(f'Файл БД не знайдено: {db_path}')


    def _backup_postgresql(self):
        filename = self._timestamp_name('.sql')
        filepath = self.backup_dir / filename
        self._dump_postgresql(filepath)
        return self._file_info(filepath, has_media=False)

    def _backup_sqlite(self):
        filename = self._timestamp_name('.sqlite3')
        filepath = self.backup_dir / filename
        self._dump_sqlite(filepath)
        return self._file_info(filepath, has_media=False)

    def _pack_archive(self, db_dump_path, dump_arcname, include_media=True):
        archive_name = self._timestamp_name('.tar.gz')
        archive_path = self.backup_dir / archive_name

        has_media = False
        media_root = getattr(settings, 'MEDIA_ROOT', None)
        workspace_docs = None
        if include_media and media_root:
            media_root_path = Path(media_root)
            candidate = media_root_path / 'workspace_documents'
            if candidate.exists():
                workspace_docs = candidate
                has_media = True

        try:
            with tarfile.open(archive_path, 'w:gz') as tar:
                # 1. Add database dump
                tar.add(str(db_dump_path), arcname=dump_arcname)

                # 2. Add media workspace_documents if present
                if workspace_docs is not None:
                    tar.add(str(workspace_docs), arcname='media/workspace_documents')

                # 3. Add manifest.json
                manifest_data = {
                    'version': '1.0',
                    'format': 'tar.gz',
                    'engine': self._engine_type(),
                    'dump_file': dump_arcname,
                    'created_at': datetime.now().isoformat(),
                    'has_media': has_media,
                    'files': tar.getnames() + ['manifest.json'],
                }
                manifest_bytes = json.dumps(manifest_data, indent=2, ensure_ascii=False).encode('utf-8')
                manifest_info = tarfile.TarInfo(name='manifest.json')
                manifest_info.size = len(manifest_bytes)
                manifest_info.mtime = int(datetime.now().timestamp())
                tar.addfile(manifest_info, io.BytesIO(manifest_bytes))

            return self._file_info(archive_path, has_media=has_media)
        except Exception:
            if archive_path.exists():
                try:
                    archive_path.unlink()
                except OSError:
                    pass
            raise

    def _read_manifest(self, filepath):
        if not filepath.name.endswith('.tar.gz'):
            return None
        try:
            with tarfile.open(filepath, 'r:gz') as tar:
                manifest_file = tar.extractfile('manifest.json')
                if manifest_file:
                    return json.load(manifest_file)
        except (tarfile.TarError, json.JSONDecodeError, KeyError, OSError):
            return None
        return None

    def _inspect_archive_has_media(self, filepath):
        manifest = self._read_manifest(filepath)
        if manifest and isinstance(manifest, dict) and 'has_media' in manifest:
            return bool(manifest['has_media'])
        try:
            with tarfile.open(filepath, 'r:gz') as tar:
                return any(name.startswith('media/') for name in tar.getnames())
        except (tarfile.TarError, OSError):
            return False

    def _file_info(self, filepath, has_media=None):
        stat = filepath.stat()
        if has_media is None:
            if filepath.name.endswith('.tar.gz'):
                has_media = self._inspect_archive_has_media(filepath)
            else:
                has_media = False

        engine = connection.settings_dict['ENGINE'].split('.')[-1]
        if filepath.name.endswith('.tar.gz'):
            manifest = self._read_manifest(filepath)
            if manifest and 'engine' in manifest:
                engine = manifest['engine']

        return {
            'filename': filepath.name,
            'size': stat.st_size,
            'created_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'engine': engine,
            'has_media': has_media,
        }

    def list_backups(self):
        """Return sorted list of backup files (newest first)."""
        backups = []
        try:
            entries = list(self.backup_dir.iterdir())
        except OSError as exc:
            logger.error('Cannot read backup directory: %s', exc)
            raise RuntimeError('Не вдалося прочитати каталог резервних копій') from exc

        for path in entries:
            try:
                if (
                    path.is_file()
                    and not path.name.startswith('.')
                    and any(path.name.endswith(ext) for ext in ALLOWED_EXTENSIONS)
                ):
                    backups.append(self._file_info(path))
            except OSError as exc:
                logger.warning('Skipping unreadable backup file %s: %s', path, exc)

        backups.sort(key=lambda item: item['created_at'], reverse=True)
        return backups


    def get_backup_path(self, filename):
        """Return validated path to a backup file."""
        path = self._resolve_safe_path(filename)
        if not path.exists():
            raise FileNotFoundError('Файл не знайдено')
        return path

    def delete_backup(self, filename):
        """Delete a backup file."""
        path = self._resolve_safe_path(filename)
        if not path.exists():
            raise FileNotFoundError('Файл не знайдено')
        path.unlink()
        return {'deleted': filename}

    def _engine_type(self):
        engine = settings.DATABASES['default']['ENGINE']
        if 'postgresql' in engine:
            return 'postgresql'
        if 'sqlite' in engine:
            return 'sqlite'
        return engine.split('.')[-1]

    def _extensions_for_engine(self, engine_type):
        if engine_type == 'postgresql':
            return {'.sql'}
        if engine_type == 'sqlite':
            return {'.sqlite3', '.db'}
        return ALLOWED_EXTENSIONS

    def find_latest_backup(self):
        """Return path to the newest backup matching the current DB engine."""
        engine_type = self._engine_type()
        allowed = self._extensions_for_engine(engine_type)
        candidates = [
            path for path in self.backup_dir.iterdir()
            if path.is_file() and path.suffix in allowed
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda path: path.stat().st_mtime)

    def restore_latest_backup(self):
        """Restore the newest compatible backup file."""
        backup_path = self.find_latest_backup()
        if backup_path is None:
            return None

        engine_type = self._engine_type()
        if engine_type == 'postgresql':
            self._restore_postgresql(backup_path)
        elif engine_type == 'sqlite':
            self._restore_sqlite(backup_path)
        else:
            raise RuntimeError(f'Непідтримуваний тип БД: {engine_type}')

        return self._file_info(backup_path)

    def _run_psql(self, *extra_args):
        db = settings.DATABASES['default']
        env = os.environ.copy()
        env['PGPASSWORD'] = db.get('PASSWORD', '')

        command = [
            'psql',
            '-h', db.get('HOST', 'localhost'),
            '-p', str(db.get('PORT', '5432')),
            '-U', db.get('USER', ''),
            '-d', db.get('NAME', ''),
            '-v', 'ON_ERROR_STOP=1',
            *extra_args,
        ]

        try:
            result = subprocess.run(
                command,
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=300,
            )
        except subprocess.TimeoutExpired as exc:
            logger.error('psql timed out after 300s')
            raise RuntimeError('psql перевищив ліміт часу') from exc

        if result.returncode != 0:
            logger.error(
                'psql failed (rc=%s): %s',
                result.returncode,
                (result.stderr or '')[:500],
            )
            raise RuntimeError('psql завершився з помилкою')

        return result

    def _quote_pg_ident(self, ident):
        """Екранувати ідентифікатор PostgreSQL (без метакоманд psql)."""
        name = (ident or '').strip()
        if not _PG_IDENT_RE.fullmatch(name):
            raise ValueError('Недопустиме ім\'я користувача БД')
        return f'"{name}"'

    def _restore_postgresql(self, filepath):
        """
        DROP + restore в одному psql-скрипті з транзакцією.

        Якщо restore падає — ROLLBACK, схема не лишається порожньою.
        """
        db_user = settings.DATABASES['default'].get('USER', '')
        quoted_user = self._quote_pg_ident(db_user)
        combined = self.backup_dir / f'.restore_tmp_{datetime.now().strftime("%Y%m%d%H%M%S%f")}.sql'
        try:
            with combined.open('w', encoding='utf-8') as out:
                out.write('BEGIN;\n')
                out.write('DROP SCHEMA IF EXISTS public CASCADE;\n')
                out.write('CREATE SCHEMA public;\n')
                out.write(f'GRANT ALL ON SCHEMA public TO {quoted_user};\n')
                out.write('GRANT ALL ON SCHEMA public TO public;\n')
                with Path(filepath).open('r', encoding='utf-8', errors='replace') as src:
                    shutil.copyfileobj(src, out)
                out.write('\nCOMMIT;\n')
            self._run_psql('-v', 'ON_ERROR_STOP=1', '-f', str(combined))
        finally:
            try:
                combined.unlink(missing_ok=True)
            except OSError:
                pass

    def _restore_sqlite(self, filepath):
        db_path = Path(settings.DATABASES['default']['NAME'])
        db_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = db_path.with_suffix(db_path.suffix + '.tmp_restore')
        try:
            shutil.copy2(filepath, tmp_path)
            os.replace(tmp_path, db_path)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

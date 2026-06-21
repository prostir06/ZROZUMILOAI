"""Database backup service."""
import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db import connection

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'.sql', '.sqlite3', '.db'}


class BackupService:
    """Create and manage database backup files."""

    def __init__(self, backup_dir=None):
        self.backup_dir = Path(backup_dir or settings.BACKUP_DIR)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _timestamp_name(self, extension):
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        db_name = settings.DATABASES['default'].get('NAME', 'database')
        if isinstance(db_name, Path):
            db_name = db_name.stem
        return f'backup_{db_name}_{stamp}{extension}'

    def _resolve_safe_path(self, filename):
        path = (self.backup_dir / filename).resolve()
        if not str(path).startswith(str(self.backup_dir.resolve())):
            raise ValueError('Недопустиме ім\'я файлу')
        if path.suffix not in ALLOWED_EXTENSIONS:
            raise ValueError('Недопустимий тип файлу')
        return path

    def create_backup(self):
        """Create a new database backup and return metadata."""
        engine = settings.DATABASES['default']['ENGINE']

        if 'postgresql' in engine:
            return self._backup_postgresql()
        if 'sqlite' in engine:
            return self._backup_sqlite()

        raise RuntimeError(f'Непідтримуваний тип БД: {engine}')

    def _backup_postgresql(self):
        db = settings.DATABASES['default']
        filename = self._timestamp_name('.sql')
        filepath = self.backup_dir / filename

        env = os.environ.copy()
        env['PGPASSWORD'] = db.get('PASSWORD', '')

        command = [
            'pg_dump',
            '-h', db.get('HOST', 'localhost'),
            '-p', str(db.get('PORT', '5432')),
            '-U', db.get('USER', ''),
            '-d', db.get('NAME', ''),
            '-f', str(filepath),
            '--clean',
            '--if-exists',
            '--no-owner',
            '--no-acl',
        ]

        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            logger.error('pg_dump failed: %s', result.stderr)
            raise RuntimeError(result.stderr or 'pg_dump завершився з помилкою')

        return self._file_info(filepath)

    def _backup_sqlite(self):
        db_path = Path(settings.DATABASES['default']['NAME'])
        if not db_path.exists():
            raise FileNotFoundError(f'Файл БД не знайдено: {db_path}')

        filename = self._timestamp_name('.sqlite3')
        filepath = self.backup_dir / filename
        shutil.copy2(db_path, filepath)
        return self._file_info(filepath)

    def _file_info(self, filepath):
        stat = filepath.stat()
        return {
            'filename': filepath.name,
            'size': stat.st_size,
            'created_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'engine': connection.settings_dict['ENGINE'].split('.')[-1],
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
                if path.is_file() and path.suffix in ALLOWED_EXTENSIONS:
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

        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            logger.error('psql failed: %s', result.stderr)
            raise RuntimeError(result.stderr or 'psql завершився з помилкою')

        return result

    def _reset_postgresql_schema(self):
        db_user = settings.DATABASES['default'].get('USER', '')
        reset_sql = (
            'DROP SCHEMA IF EXISTS public CASCADE; '
            'CREATE SCHEMA public; '
            f'GRANT ALL ON SCHEMA public TO {db_user}; '
            'GRANT ALL ON SCHEMA public TO public;'
        )
        self._run_psql('-c', reset_sql)

    def _restore_postgresql(self, filepath):
        self._reset_postgresql_schema()
        self._run_psql('-f', str(filepath))

    def _restore_sqlite(self, filepath):
        db_path = Path(settings.DATABASES['default']['NAME'])
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if db_path.exists():
            db_path.unlink()
        shutil.copy2(filepath, db_path)

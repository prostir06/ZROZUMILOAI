"""Database backup service (facade over engine submodules)."""
import logging
import re
import tarfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db import connection

from backups.engine import archive, postgres, sqlite
from backups.engine.archive import ALLOWED_EXTENSIONS

logger = logging.getLogger(__name__)


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
        return archive.resolve_safe_path(self.backup_dir, filename)

    def _read_manifest(self, filepath):
        return archive.read_manifest(filepath)

    def _unpack_media_member(self, tar, member, media_root):
        return archive.unpack_media_member(tar, member, media_root)

    def _dump_postgresql(self, target_filepath):
        return postgres.dump_postgresql(target_filepath, settings.DATABASES['default'])

    def _dump_sqlite(self, target_filepath):
        return sqlite.dump_sqlite(target_filepath, settings.DATABASES['default'])

    def _run_psql(self, *extra_args):
        return postgres.run_psql(settings.DATABASES['default'], *extra_args)

    def _quote_pg_ident(self, ident):
        return postgres.quote_pg_ident(ident)

    def _restore_postgresql(self, filepath):
        return postgres.restore_postgresql(
            filepath=filepath,
            db_config=settings.DATABASES['default'],
            backup_dir=self.backup_dir,
            run_psql_fn=self._run_psql,
        )

    def _restore_sqlite(self, filepath):
        return sqlite.restore_sqlite(filepath, settings.DATABASES['default'])

    def _pack_archive(self, db_dump_path, dump_arcname, include_media=True):
        archive_name = self._timestamp_name('.tar.gz')
        archive_path = archive.pack_archive(
            backup_dir=self.backup_dir,
            db_dump_path=db_dump_path,
            dump_arcname=dump_arcname,
            include_media=include_media,
            engine_type=self._engine_type(),
            archive_name=archive_name,
        )
        return self._file_info(archive_path)

    def _restore_archive(self, backup_path, engine_type):
        def restore_dump_fn(target_dump_file):
            if engine_type == 'postgresql':
                self._restore_postgresql(target_dump_file)
            elif engine_type == 'sqlite':
                self._restore_sqlite(target_dump_file)
            else:
                raise RuntimeError(f'Непідтримуваний тип БД: {engine_type}')

        return archive.restore_archive(
            backup_dir=self.backup_dir,
            backup_path=backup_path,
            engine_type=engine_type,
            restore_dump_fn=restore_dump_fn,
            unpack_media_fn=self._unpack_media_member,
            file_info_fn=self._file_info,
        )

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
                except OSError as exc:
                    logger.warning('Failed to remove temp dump file %s: %s', temp_dump, exc)

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

    def _file_info(self, filepath, has_media=None):
        stat = filepath.stat()
        engine = connection.settings_dict['ENGINE'].split('.')[-1]

        if filepath.name.endswith('.tar.gz'):
            manifest = self._read_manifest(filepath)
            if manifest and isinstance(manifest, dict):
                if has_media is None and 'has_media' in manifest:
                    has_media = bool(manifest['has_media'])
                if 'engine' in manifest:
                    engine = manifest['engine']
            if has_media is None:
                try:
                    with tarfile.open(filepath, 'r:gz') as tar:
                        has_media = any(name.startswith('media/') for name in tar.getnames())
                except (tarfile.TarError, OSError) as exc:
                    logger.debug('Could not inspect media entries in %s: %s', filepath.name, exc)
                    has_media = False
        else:
            if has_media is None:
                has_media = False

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
            return {'.sql', '.tar.gz'}
        if engine_type == 'sqlite':
            return {'.sqlite3', '.db', '.tar.gz'}
        return ALLOWED_EXTENSIONS

    def _is_compatible_backup(self, path, engine_type):
        if path.name.endswith('.tar.gz'):
            manifest = self._read_manifest(path)
            if manifest and isinstance(manifest, dict):
                if 'engine' in manifest:
                    return manifest['engine'] == engine_type
                if 'dump_file' in manifest:
                    if engine_type == 'postgresql':
                        return manifest['dump_file'].endswith('.sql')
                    if engine_type == 'sqlite':
                        return any(manifest['dump_file'].endswith(ext) for ext in ('.sqlite3', '.db'))
            try:
                with tarfile.open(path, 'r:gz') as tar:
                    names = tar.getnames()
                    if engine_type == 'postgresql':
                        return 'dump.sql' in names
                    if engine_type == 'sqlite':
                        return any(n in names for n in ('dump.sqlite3', 'dump.db'))
            except (tarfile.TarError, OSError) as exc:
                logger.debug('Compatibility check error for %s: %s', path.name, exc)
                return False
            return False

        if engine_type == 'postgresql':
            return path.name.endswith('.sql')
        if engine_type == 'sqlite':
            return any(path.name.endswith(ext) for ext in ('.sqlite3', '.db'))
        return any(path.name.endswith(ext) for ext in ALLOWED_EXTENSIONS)

    def find_latest_backup(self):
        """Return path to the newest backup matching the current DB engine."""
        engine_type = self._engine_type()
        candidates = []
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
                    and self._is_compatible_backup(path, engine_type)
                ):
                    candidates.append(path)
            except OSError as exc:
                logger.warning('Failed to inspect backup candidate %s: %s', path.name, exc)
                continue

        if not candidates:
            return None
        return max(candidates, key=lambda path: path.stat().st_mtime)

    def restore_backup(self, filename):
        """Restore database and optional media from a backup file."""
        backup_path = self.get_backup_path(filename)
        engine_type = self._engine_type()

        if backup_path.name.endswith('.tar.gz'):
            return self._restore_archive(backup_path, engine_type)

        if backup_path.name.endswith('.sql'):
            if engine_type != 'postgresql':
                raise RuntimeError(f'Дамп {backup_path.name} не підтримується для рушія {engine_type}')
            self._restore_postgresql(backup_path)
            return self._file_info(backup_path)

        if any(backup_path.name.endswith(ext) for ext in ('.sqlite3', '.db')):
            if engine_type != 'sqlite':
                raise RuntimeError(f'Дамп {backup_path.name} не підтримується для рушія {engine_type}')
            self._restore_sqlite(backup_path)
            return self._file_info(backup_path)

        raise ValueError('Недопустимий тип файлу')

    def restore_latest_backup(self):
        """Restore the newest compatible backup file."""
        backup_path = self.find_latest_backup()
        if backup_path is None:
            return None
        return self.restore_backup(backup_path.name)

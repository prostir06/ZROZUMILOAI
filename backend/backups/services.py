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
                except (tarfile.TarError, OSError):
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
            except (tarfile.TarError, OSError):
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
            except OSError:
                continue

        if not candidates:
            return None
        return max(candidates, key=lambda path: path.stat().st_mtime)

    def _unpack_media_member(self, tar, member, media_root):
        norm_name = member.name.replace('\\', '/')
        if norm_name == 'media' or norm_name == 'media/':
            return
        if not norm_name.startswith('media/'):
            return

        rel_path = norm_name[len('media/'):].lstrip('/')
        if not rel_path:
            return

        parts = Path(rel_path).parts
        if '..' in parts or any(part.startswith('/') or part.startswith('\\') for part in parts):
            raise ValueError(f"Небезпечний шлях у резервній копії: {member.name}")

        if Path(rel_path).is_absolute() or (len(rel_path) > 1 and rel_path[1] == ':'):
            raise ValueError(f"Небезпечний шлях у резервній копії: {member.name}")

        if member.issym() or member.islnk():
            raise ValueError(f"Небезпечний тип запису у резервній копії: {member.name}")

        media_root_resolved = media_root.resolve()
        target_path = (media_root_resolved / rel_path).resolve()

        try:
            if os.path.commonpath([str(media_root_resolved), str(target_path)]) != str(media_root_resolved):
                raise ValueError(f"Небезпечний шлях у резервній копії: {member.name}")
        except ValueError:
            raise ValueError(f"Небезпечний шлях у резервній копії: {member.name}")

        if member.isdir():
            target_path.mkdir(parents=True, exist_ok=True)
        elif member.isfile():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            src = tar.extractfile(member)
            if src is not None:
                with open(target_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
        else:
            raise ValueError(f"Небезпечний тип запису у резервній копії: {member.name}")

    def _restore_archive(self, backup_path, engine_type):
        tmp_restore_dir = self.backup_dir / f'.tmp_restore_{datetime.now().strftime("%Y%m%d%H%M%S%f")}'
        tmp_restore_dir.mkdir(parents=True, exist_ok=True)

        try:
            with tarfile.open(backup_path, 'r:gz') as tar:
                members = tar.getmembers()
                member_names = [m.name for m in members]

                manifest = None
                try:
                    manifest_file = tar.extractfile('manifest.json')
                    if manifest_file:
                        manifest = json.load(manifest_file)
                except Exception:
                    manifest = None

                dump_filename = None
                if manifest and isinstance(manifest, dict) and 'dump_file' in manifest:
                    dump_filename = manifest['dump_file']
                elif 'dump.sql' in member_names:
                    dump_filename = 'dump.sql'
                elif 'dump.sqlite3' in member_names:
                    dump_filename = 'dump.sqlite3'
                elif 'dump.db' in member_names:
                    dump_filename = 'dump.db'

                if not dump_filename or dump_filename not in member_names:
                    raise RuntimeError('Архів не містить дампа бази даних')

                if dump_filename.endswith('.sql') and engine_type != 'postgresql':
                    raise RuntimeError(f"Дамп {dump_filename} не підтримується для рушія {engine_type}")
                if dump_filename.endswith(('.sqlite3', '.db')) and engine_type != 'sqlite':
                    raise RuntimeError(f"Дамп {dump_filename} не підтримується для рушія {engine_type}")

                media_members = [
                    m for m in members
                    if m.name == 'media' or m.name.startswith(('media/', 'media\\'))
                ]
                if media_members:
                    media_root = getattr(settings, 'MEDIA_ROOT', None)
                    if not media_root:
                        raise RuntimeError('MEDIA_ROOT не налаштовано')
                    media_root_path = Path(media_root).resolve()
                    media_root_path.mkdir(parents=True, exist_ok=True)

                    for m in media_members:
                        self._unpack_media_member(tar, m, media_root_path)

                dump_member = tar.getmember(dump_filename)
                target_dump_file = tmp_restore_dir / dump_filename
                dump_src = tar.extractfile(dump_member)
                if dump_src is None:
                    raise RuntimeError(f'Не вдалося прочитати {dump_filename} з архіву')
                with open(target_dump_file, 'wb') as dump_dst:
                    shutil.copyfileobj(dump_src, dump_dst)

            if engine_type == 'postgresql':
                self._restore_postgresql(target_dump_file)
            elif engine_type == 'sqlite':
                self._restore_sqlite(target_dump_file)
            else:
                raise RuntimeError(f'Непідтримуваний тип БД: {engine_type}')

            return self._file_info(backup_path)
        finally:
            shutil.rmtree(tmp_restore_dir, ignore_errors=True)

    def restore_backup(self, filename):
        """Restore database and optional media from a backup file."""
        backup_path = self.get_backup_path(filename)
        engine_type = self._engine_type()

        if backup_path.name.endswith('.tar.gz'):
            return self._restore_archive(backup_path, engine_type)

        if backup_path.name.endswith('.sql'):
            if engine_type != 'postgresql':
                raise RuntimeError(f"Дамп {backup_path.name} не підтримується для рушія {engine_type}")
            self._restore_postgresql(backup_path)
            return self._file_info(backup_path)

        if any(backup_path.name.endswith(ext) for ext in ('.sqlite3', '.db')):
            if engine_type != 'sqlite':
                raise RuntimeError(f"Дамп {backup_path.name} не підтримується для рушія {engine_type}")
            self._restore_sqlite(backup_path)
            return self._file_info(backup_path)

        raise ValueError('Недопустимий тип файлу')

    def restore_latest_backup(self):
        """Restore the newest compatible backup file."""
        backup_path = self.find_latest_backup()
        if backup_path is None:
            return None
        return self.restore_backup(backup_path.name)

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
        connection.close()
        try:
            shutil.copy2(filepath, tmp_path)
            os.replace(tmp_path, db_path)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

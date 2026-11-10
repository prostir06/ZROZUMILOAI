"""Archive creation, validation, and extraction engine."""
import io
import json
import logging
import os
import shutil
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

from django.conf import settings

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'.sql', '.sqlite3', '.db', '.tar.gz'}


def resolve_safe_path(backup_dir: Union[Path, str], filename: str) -> Path:
    """Перевірити безпечність шляху до backup-файлу та його розширення."""
    base = Path(backup_dir).resolve()
    path = (base / filename).resolve()
    if not (path == base or base in path.parents):
        raise ValueError("Недопустиме ім'я файлу")
    if not any(path.name.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        raise ValueError('Недопустимий тип файлу')
    return path


def read_manifest(filepath: Union[Path, str]) -> Optional[Dict[str, Any]]:
    """Прочитати manifest.json з архіву .tar.gz, якщо присутній."""
    filepath = Path(filepath)
    if not filepath.name.endswith('.tar.gz'):
        return None
    try:
        with tarfile.open(filepath, 'r:gz') as tar:
            manifest_file = tar.extractfile('manifest.json')
            if manifest_file:
                return json.load(manifest_file)
    except (tarfile.TarError, json.JSONDecodeError, KeyError, OSError) as exc:
        logger.debug('Cannot read manifest from %s: %s', filepath, exc)
        return None
    return None


def unpack_media_member(
    tar: tarfile.TarFile,
    member: tarfile.TarInfo,
    media_root: Path,
) -> None:
    """Безпечно розпакувати елемент медіа з архіву."""
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
    except ValueError as exc:
        raise ValueError(f"Небезпечний шлях у резервній копії: {member.name}") from exc

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


def pack_archive(
    backup_dir: Union[Path, str],
    db_dump_path: Union[Path, str],
    dump_arcname: str,
    include_media: bool = True,
    engine_type: Optional[str] = None,
    archive_name: Optional[str] = None,
) -> Path:
    """Запакувати дамп бази та медіа-файли в .tar.gz з manifest.json на початку."""
    backup_dir_path = Path(backup_dir)
    if not archive_name:
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        archive_name = f'backup_{stamp}.tar.gz'
    archive_path = backup_dir_path / archive_name

    if engine_type is None:
        if dump_arcname.endswith('.sql'):
            engine_type = 'postgresql'
        elif any(dump_arcname.endswith(ext) for ext in ('.sqlite3', '.db')):
            engine_type = 'sqlite'
        else:
            engine_type = 'unknown'

    has_media = False
    media_root = getattr(settings, 'MEDIA_ROOT', None)
    workspace_docs = None
    if include_media and media_root:
        media_root_path = Path(media_root)
        candidate = media_root_path / 'workspace_documents'
        if candidate.exists():
            workspace_docs = candidate
            has_media = True

    files_list = ['manifest.json', dump_arcname]
    if workspace_docs is not None:
        files_list.append('media/workspace_documents')

    # Prepare manifest metadata in advance so it is written as the first entry in the tar stream
    manifest_data = {
        'version': '1.0',
        'format': 'tar.gz',
        'engine': engine_type,
        'dump_file': dump_arcname,
        'created_at': datetime.now().isoformat(),
        'has_media': has_media,
        'files': files_list,
    }
    manifest_bytes = json.dumps(manifest_data, indent=2, ensure_ascii=False).encode('utf-8')
    manifest_info = tarfile.TarInfo(name='manifest.json')
    manifest_info.size = len(manifest_bytes)
    manifest_info.mtime = int(datetime.now().timestamp())

    try:
        with tarfile.open(archive_path, 'w:gz') as tar:
            # 1. Add manifest.json first (allows fast O(1) reads without decompressing dump or media)
            tar.addfile(manifest_info, io.BytesIO(manifest_bytes))

            # 2. Add database dump
            tar.add(str(db_dump_path), arcname=dump_arcname)

            # 3. Add media workspace_documents if present
            if workspace_docs is not None:
                tar.add(str(workspace_docs), arcname='media/workspace_documents')

        return archive_path
    except Exception as exc:
        logger.error('Failed to pack backup archive %s: %s', archive_path, exc, exc_info=True)
        if archive_path.exists():
            try:
                archive_path.unlink()
            except OSError as unlink_err:
                logger.warning('Failed to remove partial archive %s: %s', archive_path, unlink_err)
        raise


def restore_archive(
    backup_dir: Union[Path, str],
    backup_path: Union[Path, str],
    engine_type: str,
    restore_dump_fn: Callable[[Path], None],
    unpack_media_fn: Optional[Callable[[tarfile.TarFile, tarfile.TarInfo, Path], None]] = None,
    file_info_fn: Optional[Callable[[Path], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Розпакувати .tar.gz архів, відновити медіа-файли та передати дамп для відновлення БД."""
    backup_dir_path = Path(backup_dir)
    backup_path = Path(backup_path)
    tmp_restore_dir = backup_dir_path / f'.tmp_restore_{datetime.now().strftime("%Y%m%d%H%M%S%f")}'
    tmp_restore_dir.mkdir(parents=True, exist_ok=True)

    if unpack_media_fn is None:
        unpack_media_fn = unpack_media_member

    try:
        with tarfile.open(backup_path, 'r:gz') as tar:
            members = tar.getmembers()
            member_names = [m.name for m in members]

            manifest = None
            try:
                if 'manifest.json' in member_names:
                    manifest_file = tar.extractfile('manifest.json')
                    if manifest_file:
                        manifest = json.load(manifest_file)
            except (tarfile.TarError, json.JSONDecodeError, KeyError, OSError) as exc:
                logger.warning('Failed to parse manifest in %s: %s', backup_path.name, exc)
                manifest = None

            dump_filename = None
            if manifest and isinstance(manifest, dict) and 'dump_file' in manifest:
                raw_dump_name = manifest['dump_file']
                sanitized_name = Path(str(raw_dump_name)).name
                if sanitized_name and sanitized_name in member_names:
                    dump_filename = sanitized_name

            if not dump_filename:
                for fallback in ('dump.sql', 'dump.sqlite3', 'dump.db'):
                    if fallback in member_names:
                        dump_filename = fallback
                        break

            if not dump_filename:
                raise RuntimeError('Архів не містить валідного дампа бази даних')

            dump_member = tar.getmember(dump_filename)
            if not dump_member.isfile():
                raise RuntimeError(f'Елемент {dump_filename} не є файлом')

            if dump_filename.endswith('.sql') and engine_type != 'postgresql':
                raise RuntimeError(f'Дамп {dump_filename} не підтримується для рушія {engine_type}')
            if dump_filename.endswith(('.sqlite3', '.db')) and engine_type != 'sqlite':
                raise RuntimeError(f'Дамп {dump_filename} не підтримується для рушія {engine_type}')

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
                    unpack_media_fn(tar, m, media_root_path)

            dump_member = tar.getmember(dump_filename)
            target_dump_file = tmp_restore_dir / dump_filename
            dump_src = tar.extractfile(dump_member)
            if dump_src is None:
                raise RuntimeError(f'Не вдалося прочитати {dump_filename} з архіву')
            with open(target_dump_file, 'wb') as dump_dst:
                shutil.copyfileobj(dump_src, dump_dst)

        restore_dump_fn(target_dump_file)

        if file_info_fn is not None:
            return file_info_fn(backup_path)

        stat = backup_path.stat()
        return {
            'filename': backup_path.name,
            'size': stat.st_size,
            'created_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'engine': engine_type,
            'has_media': bool(media_members),
        }
    finally:
        shutil.rmtree(tmp_restore_dir, ignore_errors=True)

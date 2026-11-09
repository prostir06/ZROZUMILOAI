"""SQLite backup and restore engine."""
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Union

from django.db import connection

logger = logging.getLogger(__name__)


def dump_sqlite(
    target_filepath: Union[Path, str],
    db_config: Dict[str, Any],
) -> None:
    """Створити дамп бази даних SQLite."""
    target_filepath = Path(target_filepath)
    db_name = db_config.get('NAME')
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


def restore_sqlite(
    filepath: Union[Path, str],
    db_config: Dict[str, Any],
) -> None:
    """Відновити базу даних SQLite з файлу."""
    filepath = Path(filepath)
    db_name = db_config.get('NAME')
    if not db_name:
        raise ValueError('Не вказано назву/шлях SQLite БД')
    db_path = Path(db_name)
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
            except OSError as exc:
                logger.warning('Failed to remove temp SQLite restore file %s: %s', tmp_path, exc)

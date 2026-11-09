"""PostgreSQL backup and restore engine."""
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

logger = logging.getLogger(__name__)

_PG_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def quote_pg_ident(ident: str) -> str:
    """Екранувати ідентифікатор PostgreSQL (без метакоманд psql)."""
    name = (ident or '').strip()
    if not _PG_IDENT_RE.fullmatch(name):
        raise ValueError("Недопустиме ім'я користувача БД")
    return f'"{name}"'


def run_psql(
    db_config: Dict[str, Any],
    *extra_args: str,
    timeout: int = 300,
) -> subprocess.CompletedProcess:
    """Виконати команду psql з налаштуваннями БД."""
    env = os.environ.copy()
    env['PGPASSWORD'] = db_config.get('PASSWORD', '')

    command = [
        'psql',
        '-h', db_config.get('HOST', 'localhost'),
        '-p', str(db_config.get('PORT', '5432')),
        '-U', db_config.get('USER', ''),
        '-d', db_config.get('NAME', ''),
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
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        logger.error('psql timed out after %ss', timeout)
        raise RuntimeError('psql перевищив ліміт часу') from exc

    if result.returncode != 0:
        logger.error(
            'psql failed (rc=%s): %s',
            result.returncode,
            (result.stderr or '')[:500],
        )
        raise RuntimeError('psql завершився з помилкою')

    return result


def dump_postgresql(
    target_filepath: Union[Path, str],
    db_config: Dict[str, Any],
    timeout: int = 300,
) -> None:
    """Створити дамп бази даних PostgreSQL через pg_dump."""
    env = os.environ.copy()
    env['PGPASSWORD'] = db_config.get('PASSWORD', '')

    command = [
        'pg_dump',
        '-h', db_config.get('HOST', 'localhost'),
        '-p', str(db_config.get('PORT', '5432')),
        '-U', db_config.get('USER', ''),
        '-d', db_config.get('NAME', ''),
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
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        logger.error('pg_dump timed out after %ss', timeout)
        raise RuntimeError('pg_dump перевищив ліміт часу') from exc

    if result.returncode != 0:
        logger.error(
            'pg_dump failed (rc=%s): %s',
            result.returncode,
            (result.stderr or '')[:500],
        )
        raise RuntimeError('pg_dump завершився з помилкою')


def restore_postgresql(
    filepath: Union[Path, str],
    db_config: Dict[str, Any],
    backup_dir: Optional[Union[Path, str]] = None,
    run_psql_fn: Optional[Callable[..., Any]] = None,
) -> None:
    """
    DROP + restore в одному psql-скрипті з транзакцією.

    Якщо restore падає — ROLLBACK, схема не лишається порожньою.
    """
    db_user = db_config.get('USER', '')
    quoted_user = quote_pg_ident(db_user)

    target_dir = Path(backup_dir) if backup_dir else Path(filepath).parent
    combined = target_dir / f'.restore_tmp_{datetime.now().strftime("%Y%m%d%H%M%S%f")}.sql'

    executor = run_psql_fn if run_psql_fn is not None else (lambda *args: run_psql(db_config, *args))

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
        executor('-v', 'ON_ERROR_STOP=1', '-f', str(combined))
    finally:
        try:
            combined.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning('Failed to remove temp SQL restore file %s: %s', combined, exc)

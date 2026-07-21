"""
Фонова індексація документів workspace через Celery.

Якщо Redis/Celery недоступні (локальна розробка), fallback на daemon-thread
після transaction.on_commit — щоб upload API не блокувався.
"""
import logging
import threading

from celery import shared_task
from django.conf import settings
from django.db import close_old_connections, transaction

logger = logging.getLogger(__name__)


def ingest_document_by_id(document_id):
    """
    Завантажити документ з БД і виконати RAG ingest.

    Безпечно викликати з Celery worker або фонового потоку.
    """
    close_old_connections()
    try:
        from workspaces.models import WorkspaceDocument
        from workspaces.rag.service import ingest_workspace_document

        try:
            document = WorkspaceDocument.objects.select_related('workspace').get(
                pk=document_id,
            )
        except WorkspaceDocument.DoesNotExist:
            logger.error('Document %s not found for background ingest', document_id)
            return {'ok': False, 'error': 'not_found'}

        try:
            ingest_workspace_document(document)
            return {'ok': True, 'document_id': document_id}
        except Exception as exc:
            logger.error(
                'Background ingest failed for document %s: %s',
                document_id,
                exc,
            )
            return {'ok': False, 'error': str(exc)[:500]}
    finally:
        close_old_connections()


@shared_task(
    bind=True,
    name='workspaces.ingest_document',
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(ConnectionError, OSError, TimeoutError),
    retry_backoff=True,
    retry_jitter=True,
)
def ingest_document_task(self, document_id):
    """Celery task: індексація документа з автоматичним retry мережевих збоїв."""
    result = ingest_document_by_id(document_id)
    if result.get('ok'):
        return result
    # Бізнес-помилки ingest (bad file тощо) не ретраїмо — статус уже FAILED.
    return result


def _enqueue_celery(document_id):
    """Спробувати поставити задачу в Celery; False якщо брокер недоступний."""
    if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
        ingest_document_task.delay(document_id)
        return True
    try:
        ingest_document_task.delay(document_id)
        return True
    except Exception as exc:
        logger.warning(
            'Celery enqueue failed for document %s: %s',
            document_id,
            exc,
        )
        return False


def _enqueue_thread(document_id):
    """Fallback: daemon thread (викликати вже після commit)."""
    thread = threading.Thread(
        target=ingest_document_by_id,
        args=(document_id,),
        name=f'ingest-doc-{document_id}',
        daemon=True,
    )
    try:
        thread.start()
    except Exception as exc:
        logger.exception(
            'Thread start failed for document %s: %s; running sync',
            document_id,
            exc,
        )
        ingest_document_by_id(document_id)


def schedule_document_ingest(document_id):
    """
    Запланувати ingest після успішного commit поточного запиту.

    Порядок: Celery → thread fallback.
    """
    def _start():
        if not _enqueue_celery(document_id):
            _enqueue_thread(document_id)

    try:
        transaction.on_commit(_start)
    except Exception as exc:
        logger.exception(
            'on_commit failed for %s, enqueue immediately: %s',
            document_id,
            exc,
        )
        if not _enqueue_celery(document_id):
            ingest_document_by_id(document_id)

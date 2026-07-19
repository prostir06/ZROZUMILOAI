"""
Фонова індексація документів workspace.

P0: HTTP-запит upload не чекає на embeddings — ingest запускається
після commit транзакції в daemon-потоці (сумісно з Gunicorn/gevent).
"""
import logging
import threading

from django.db import close_old_connections, transaction

logger = logging.getLogger(__name__)


def ingest_document_by_id(document_id):
    """
    Завантажити документ з БД і виконати RAG ingest.

    Безпечно викликати з фонового потоку: закриває старі DB-з'єднання.
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
            return

        try:
            ingest_workspace_document(document)
        except Exception as exc:
            # ingest_workspace_document вже оновлює status=failed
            logger.error(
                'Background ingest failed for document %s: %s',
                document_id,
                exc,
            )
    finally:
        close_old_connections()


def schedule_document_ingest(document_id):
    """
    Запланувати ingest після успішного commit поточного запиту.

    Використання:
        document = WorkspaceDocument.objects.create(...)
        schedule_document_ingest(document.pk)
    """
    def _start():
        thread = threading.Thread(
            target=ingest_document_by_id,
            args=(document_id,),
            name=f'ingest-doc-{document_id}',
            daemon=True,
        )
        thread.start()

    try:
        transaction.on_commit(_start)
    except Exception as exc:
        logger.exception(
            'Failed to schedule ingest for %s, running inline: %s',
            document_id,
            exc,
        )
        ingest_document_by_id(document_id)

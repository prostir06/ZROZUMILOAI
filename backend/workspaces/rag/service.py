"""
Фасад RAG: реекспорт модулів ingest / search / fusion / format.

Новий код імпортує з підмодулів; service лишається стабільним API.
"""
import re
from pathlib import Path

from django.db.models import Count, Sum

from ollama_proxy.services import OllamaService  # noqa: F401 — patches у тестах
from .python_search import search_with_python  # noqa: F401
from .text_extractor import extract_text_from_file  # noqa: F401
from .vector_search import uses_pgvector  # noqa: F401

from ..models import WorkspaceDocument
from .format_context import (  # noqa: F401
    chunk_relevance_score,
    format_rag_context,
    sources_from_chunks,
)
from .fusion import RRF_K, reciprocal_rank_fusion  # noqa: F401
from .ingest import _embed_texts_parallel, ingest_workspace_document  # noqa: F401
from .search_context import (  # noqa: F401
    cached_query_embedding,
    search_workspace_context,
    search_workspace_documents,
)

# Зворотна сумісність імен для тестів / старих імпортів.
_cached_query_embedding = cached_query_embedding
_chunk_relevance_score = chunk_relevance_score


def workspace_rag_stats(workspace):
    """Агрегована статистика RAG для адмінки."""
    docs = workspace.documents.all()
    by_status = {
        row['status']: row['count']
        for row in docs.values('status').annotate(count=Count('id'))
    }
    chunk_total = docs.aggregate(total=Sum('chunk_count'))['total'] or 0
    return {
        'documents_total': docs.count(),
        'documents_ready': by_status.get(WorkspaceDocument.Status.READY, 0),
        'documents_processing': by_status.get(
            WorkspaceDocument.Status.PROCESSING, 0,
        ),
        'documents_failed': by_status.get(WorkspaceDocument.Status.FAILED, 0),
        'chunks_total': chunk_total,
    }


def extract_last_user_message(messages):
    """Отримати текст останнього user-повідомлення з історії чату."""
    if not isinstance(messages, list):
        return None

    for message in reversed(messages):
        if (
            isinstance(message, dict)
            and message.get('role') == 'user'
            and isinstance(message.get('content'), str)
        ):
            text = message['content'].strip()
            if text:
                return text
    return None


def sanitize_filename(filename):
    """Безпечне ім'я файлу без шляхів."""
    name = Path(filename).name if filename else 'document'
    name = re.sub(r'[^\w.\- ]', '_', name, flags=re.UNICODE)
    return name[:200] or 'document'

"""Пошук контексту: internal RAG, Meili, hybrid RRF."""
import hashlib
import logging

from django.conf import settings
from django.core.cache import cache

from ollama_proxy.services import OllamaService

from ..models import Workspace
from .fusion import reciprocal_rank_fusion
from .python_search import search_with_python
from .vector_search import search_with_pgvector, uses_pgvector

logger = logging.getLogger(__name__)


def search_workspace_context(workspace, query, top_k=None, course_id=None):
    """
    Зібрати контекст з локального RAG та/або Meilisearch Open edX.

    Hybrid: RRF. Пошук послідовний (без ThreadPool) — безпечніше під gevent.
    """
    if not workspace or not query or not query.strip():
        return []

    top_k = top_k or settings.RAG_TOP_K
    source = workspace.search_source or Workspace.SearchSource.INTERNAL
    use_internal = source in (
        Workspace.SearchSource.INTERNAL,
        Workspace.SearchSource.HYBRID,
    )
    use_meili = source in (
        Workspace.SearchSource.MEILISEARCH,
        Workspace.SearchSource.HYBRID,
    )

    if use_internal and use_meili:
        internal, meili = _search_hybrid_lists(workspace, query, top_k, course_id)
        return reciprocal_rank_fusion([internal, meili], top_k=top_k)

    chunks = []
    if use_internal:
        chunks.extend(search_workspace_documents(workspace, query, top_k=top_k))
    if use_meili:
        from .meilisearch_search import search_openedx_meilisearch

        chunks.extend(
            search_openedx_meilisearch(
                workspace,
                query,
                top_k=top_k,
                course_id=course_id,
            ),
        )

    if not chunks:
        return []

    chunks.sort(key=lambda item: item.get('score', 0), reverse=True)
    return chunks[:top_k]


def _search_hybrid_lists(workspace, query, top_k, course_id):
    """Послідовно отримати internal + Meili (для RRF; без ThreadPool під gevent)."""
    from .meilisearch_search import search_openedx_meilisearch

    internal = []
    meili = []
    try:
        internal = search_workspace_documents(workspace, query, top_k=top_k) or []
    except Exception as exc:
        logger.error('Hybrid internal search failed: %s', exc)
    try:
        meili = search_openedx_meilisearch(
            workspace,
            query,
            top_k=top_k,
            course_id=course_id,
        ) or []
    except Exception as exc:
        logger.error('Hybrid meilisearch failed: %s', exc)
    return internal, meili


def search_workspace_documents(workspace, query, top_k=None):
    """Знайти найрелевантніші фрагменти документів workspace."""
    if not settings.RAG_ENABLED or not workspace or not query or not query.strip():
        return []

    top_k = top_k or settings.RAG_TOP_K
    query_text = query.strip()

    try:
        query_vector = cached_query_embedding(
            workspace_id=workspace.pk,
            query=query_text,
        )
    except Exception as exc:
        logger.error('RAG query embedding failed: %s', exc)
        return []

    try:
        if uses_pgvector():
            return search_with_pgvector(workspace, query_vector, top_k)
        return search_with_python(workspace, query_vector, top_k)
    except Exception as exc:
        logger.error('RAG search failed: %s', exc)
        return []


def cached_query_embedding(workspace_id, query):
    """
    Embed запиту з коротким кешем (Redis/FileBased).

    Gemini-workspaces також використовують Ollama для embeddings.
    """
    embed_model = settings.RAG_EMBED_MODEL
    digest = hashlib.sha256(query.encode('utf-8')).hexdigest()
    try:
        ws_key = str(int(workspace_id))
    except (TypeError, ValueError):
        ws_key = 'anon'
    cache_key = f'rag:qemb:{ws_key}:{embed_model}:{digest}'
    ttl = int(getattr(settings, 'RAG_QUERY_EMBED_CACHE_TTL', 300))

    try:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
    except Exception as exc:
        logger.warning('Failed to read query embedding cache: %s', exc)

    ollama = OllamaService()
    vector = ollama.embed(embed_model, query)
    try:
        cache.set(cache_key, vector, timeout=ttl)
    except Exception as exc:
        logger.warning('Failed to cache query embedding: %s', exc)
    return vector

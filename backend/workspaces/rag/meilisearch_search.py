"""Пошук у Meilisearch Open edX (Tutor)."""
import logging
from urllib.parse import urlparse

import meilisearch
from django.conf import settings

from ..models import Workspace
from .text_utils import strip_html, truncate_text

logger = logging.getLogger(__name__)

OPENEDX_DEFAULT_INDEX_SUFFIXES = ('course_info', 'courseware_content')

OPENEDX_CONTENT_TEXT_KEYS = (
    'display_name',
    'overview',
    'short_description',
    'description',
    'notes',
    'title',
)


def normalize_meilisearch_url(url):
    """Додати схему, якщо в URL її немає."""
    value = (url or '').strip()
    if not value:
        return ''

    parsed = urlparse(value)
    if parsed.scheme:
        # Локальний Tutor/Open edX зазвичай без TLS на Meilisearch.
        host = (parsed.hostname or '').lower()
        if (
            parsed.scheme == 'https'
            and (host.endswith('.local.openedx.io') or host.endswith('.edly.io'))
        ):
            port_suffix = f':{parsed.port}' if parsed.port else ''
            path = parsed.path or ''
            query = f'?{parsed.query}' if parsed.query else ''
            return f'http://{host}{port_suffix}{path}{query}'
        return value

    host = value.split('/')[0].lower()
    if host.endswith('.local.openedx.io') or host.endswith('.edly.io'):
        return f'http://{value}'
    return f'https://{value}'


def resolve_meilisearch_indexes(workspace):
    """
    Повернути список UID індексів Meilisearch.

    meilisearch_indexes може містити суфікси (course_info) або повні UID
    (tutor_course_info).
    """
    configured = workspace.meilisearch_indexes or []
    prefix = (workspace.meilisearch_index_prefix or '').strip()

    if configured:
        uids = []
        for entry in configured:
            name = str(entry).strip()
            if not name:
                continue
            if prefix and not name.startswith(prefix):
                uids.append(f'{prefix}{name}')
            else:
                uids.append(name)
        return uids

    if not prefix:
        prefix = getattr(settings, 'MEILISEARCH_INDEX_PREFIX', 'tutor_')

    return [f'{prefix}{suffix}' for suffix in OPENEDX_DEFAULT_INDEX_SUFFIXES]


def resolve_meilisearch_credentials(workspace):
    """URL і API key: workspace → глобальні settings → порожньо."""
    from workspaces.crypto import decrypt_secret

    url = normalize_meilisearch_url(
        workspace.meilisearch_url
        or getattr(settings, 'MEILISEARCH_URL', ''),
    )
    raw_key = (
        workspace.meilisearch_api_key
        or getattr(settings, 'MEILISEARCH_API_KEY', '')
    )
    try:
        api_key = decrypt_secret(raw_key) if raw_key else ''
    except Exception:
        api_key = raw_key or ''
    return url, api_key


def extract_openedx_hit_text(hit):
    """Витягти читабельний текст з документа Open edX у Meilisearch."""
    if not isinstance(hit, dict):
        return ''

    max_chars = settings.MEILISEARCH_MAX_CHUNK_CHARS
    parts = []
    for key in ('display_name', 'title', 'description', 'overview'):
        value = hit.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(strip_html(value.strip()))

    content = hit.get('content')
    if isinstance(content, str) and content.strip():
        parts.append(strip_html(content.strip()))
    elif isinstance(content, dict):
        for key in OPENEDX_CONTENT_TEXT_KEYS:
            value = content.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(strip_html(value.strip()))

    course = hit.get('course') or hit.get('id')
    if isinstance(course, str) and course.strip():
        parts.insert(0, f'Курс: {course.strip()}')

    if parts:
        return truncate_text('\n'.join(parts), max_chars)

    for key in ('id', 'location'):
        value = hit.get(key)
        if isinstance(value, str) and value.strip():
            return truncate_text(value.strip(), max_chars)

    return 'Фрагмент Open edX'


def extract_openedx_hit_name(hit):
    """Назва джерела для контексту RAG."""
    if not isinstance(hit, dict):
        return 'Open edX'

    for key in ('display_name', 'title'):
        value = hit.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    content = hit.get('content')
    if isinstance(content, dict):
        name = content.get('display_name')
        if isinstance(name, str) and name.strip():
            return name.strip()

    course = hit.get('course') or hit.get('id')
    if isinstance(course, str) and course.strip():
        return course.strip()

    return 'Open edX'


def build_course_filter(course_id, index_uid):
    """Фільтр Meilisearch для обмеження пошуку одним курсом."""
    if not course_id:
        return None

    course_id = course_id.strip()
    if not course_id:
        return None

    if 'courseware' in index_uid:
        return f'course = "{course_id}"'

    return f'id = "{course_id}" OR course = "{course_id}"'


def search_openedx_meilisearch(workspace, query, top_k=None, course_id=None):
    """
    Пошук у Meilisearch Open edX для workspace.

    :return: список dict з content, score, document_name
    """
    if not workspace or not query or not str(query).strip():
        return []

    if workspace.search_source not in (
        Workspace.SearchSource.MEILISEARCH,
        Workspace.SearchSource.HYBRID,
    ):
        return []

    url, api_key = resolve_meilisearch_credentials(workspace)
    if not url:
        logger.warning('Meilisearch URL не налаштовано для workspace %s', workspace.pk)
        return []

    top_k = top_k or settings.RAG_TOP_K
    index_uids = resolve_meilisearch_indexes(workspace)
    if not index_uids:
        return []

    effective_course_id = (
        (course_id or '').strip()
        or (workspace.meilisearch_course_id or '').strip()
    )

    try:
        client = meilisearch.Client(
            url,
            api_key or None,
            timeout=settings.MEILISEARCH_TIMEOUT_MS,
        )
    except Exception as exc:
        logger.error('Meilisearch client init failed: %s', exc)
        return []

    scored = []
    for index_uid in index_uids:
        try:
            index = client.index(index_uid)
            params = {'limit': top_k, 'showRankingScore': True}
            course_filter = build_course_filter(effective_course_id, index_uid)
            if course_filter:
                params['filter'] = course_filter

            result = index.search(query.strip(), params)
        except Exception as exc:
            logger.error('Meilisearch search failed (%s): %s', index_uid, exc)
            continue

        for hit in result.get('hits', []):
            score = hit.get('_rankingScore', 0.0)
            try:
                score = float(score)
            except (TypeError, ValueError):
                score = 0.0

            scored.append({
                'content': extract_openedx_hit_text(hit),
                'score': score,
                'document_name': extract_openedx_hit_name(hit),
            })

    scored.sort(key=lambda item: item['score'], reverse=True)
    return scored[:top_k]

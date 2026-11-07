"""Аналіз таблиці Chats Info локальною моделлю Ollama."""
import json
import logging
import re

from django.db.models import Count

logger = logging.getLogger(__name__)

MAX_SAMPLE_ROWS = 12
FIELD_CHARS = 120
ANALYSIS_TOKENS = 500
# Короткий контекст: інакше Gemma3 з 16k і 4 слотами не вміщається в RAM і зависає на завантаженні.
ANALYSIS_CONTEXT = 2048

_SYSTEM_PROMPT = (
    'Ти аналітик підтримки навчальних курсів. '
    'Пиши українською лише за переданими рядками, без вигаданих цифр. '
    'Не повторюй вхідний список і не повертай JSON. '
    'Формат відповіді:\n'
    'Висновок: один абзац\n'
    'Теми: тема — пояснення\n'
    'Проблеми: пункт\n'
    'Рекомендації: пункт'
)


def is_chat_model(name):
    """Embedding-моделі не підходять для текстового аналізу."""
    lowered = str(name or '').strip().lower()
    return bool(lowered) and 'embed' not in lowered


def pick_chat_model(models):
    """Gemma3, якщо вона встановлена. Інакше перша чат-модель."""
    names = []
    for model in models or []:
        if not isinstance(model, dict):
            continue
        name = str(model.get('name') or model.get('model') or '').strip()
        if is_chat_model(name):
            names.append(name)
    for name in names:
        base = name.split(':', 1)[0].lower()
        if base == 'gemma3' or base.endswith('/gemma3'):
            return name
    return names[0] if names else ''


def build_table_digest(logs):
    """Лічильники всієї вибірки і короткі рядки для промпта."""
    total = logs.count()
    handoff = logs.filter(needs_handoff=True).count()
    feedback_up = logs.filter(feedback='up').count()
    feedback_down = logs.filter(feedback='down').count()
    workspace_rows = (
        logs.values('workspace__name')
        .annotate(count=Count('id'))
        .order_by('-count')[:8]
    )
    workspaces = [
        {'name': item['workspace__name'] or '', 'count': item['count']}
        for item in workspace_rows
    ]
    rows = []
    sample = logs.select_related('workspace').order_by('-created_at')[:MAX_SAMPLE_ROWS]
    for log in sample:
        rows.append({
            'workspace': log.workspace.name if log.workspace_id else '',
            'prompt': (log.prompt or '')[:FIELD_CHARS],
            'response': (log.response or '')[:FIELD_CHARS],
            'feedback': log.feedback or '',
            'handoff': bool(log.needs_handoff),
        })
    return {
        'total': total,
        'handoff': handoff,
        'feedback_up': feedback_up,
        'feedback_down': feedback_down,
        'workspaces': workspaces,
        'rows': rows,
    }


def parse_model_analysis(text):
    """Розібрати JSON або підписи Висновок/Теми/Проблеми/Рекомендації."""
    raw = re.sub(r'<think>.*?</think>', '', text or '', flags=re.DOTALL | re.IGNORECASE)
    raw = raw.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    labeled = _parse_labels(raw)
    if _has_analysis(labeled):
        return labeled

    start = raw.find('{')
    end = raw.rfind('}')
    if start != -1 and end > start:
        try:
            payload = json.loads(raw[start:end + 1])
        except json.JSONDecodeError as exc:
            logger.warning('Chat table analysis is not JSON: %s', exc)
            payload = None
        if isinstance(payload, dict) and _has_analysis(payload):
            return {
                'summary': str(payload.get('summary') or '').strip()[:2000],
                'topics': _topics(payload.get('topics')),
                'problems': _strings(payload.get('problems')),
                'recommendations': _strings(payload.get('recommendations')),
            }
    if raw.startswith('{') or '"rows"' in raw:
        return {
            'summary': '',
            'topics': [],
            'problems': [],
            'recommendations': [],
        }
    return {
        'summary': raw[:2000],
        'topics': [],
        'problems': [],
        'recommendations': [],
    }


def analyze_chat_table(logs, provider, model):
    """Повернути дашборд. Порожню таблицю модель не викликає."""
    digest = build_table_digest(logs)
    result = {
        'model': model,
        'total': digest['total'],
        'handoff': digest['handoff'],
        'feedback_up': digest['feedback_up'],
        'feedback_down': digest['feedback_down'],
        'summary': '',
        'topics': [],
        'problems': [],
        'recommendations': [],
    }
    if digest['total'] == 0:
        result['summary'] = 'У таблиці немає записів для аналізу.'
        return result

    response = provider.chat(
        model,
        [
            {'role': 'system', 'content': _SYSTEM_PROMPT},
            {'role': 'user', 'content': _prompt_text(digest)},
        ],
        stream=False,
        options={
            'temperature': 0.2,
            'num_predict': ANALYSIS_TOKENS,
            'num_ctx': ANALYSIS_CONTEXT,
        },
    )
    content = ''
    if isinstance(response, dict):
        content = (response.get('message') or {}).get('content') or ''
    parsed = parse_model_analysis(content)
    result.update(parsed)
    return result


def _prompt_text(digest):
    lines = [
        f"Записів: {digest['total']}",
        f"Handoff: {digest['handoff']}",
        f"Корисні оцінки: {digest['feedback_up']}",
        f"Некорисні оцінки: {digest['feedback_down']}",
        'Питання:',
    ]
    for row in digest['rows']:
        mark = row['feedback'] or 'без оцінки'
        handoff = 'handoff' if row['handoff'] else 'без handoff'
        lines.append(
            f"- {row['prompt']} | {row['response']} | {mark}, {handoff}",
        )
    lines.append('Почни відповідь словом «Висновок:».')
    return '\n'.join(lines)


def _has_analysis(payload):
    if not isinstance(payload, dict):
        return False
    return any(payload.get(key) for key in (
        'summary',
        'topics',
        'problems',
        'recommendations',
    ))


def _parse_labels(text):
    buckets = {
        'висновок': 'summary',
        'теми': 'topics',
        'проблеми': 'problems',
        'рекомендації': 'recommendations',
    }
    current = None
    collected = {key: [] for key in buckets.values()}
    for line in text.splitlines():
        stripped = line.strip().lstrip('-').strip()
        if not stripped:
            continue
        key = None
        rest = stripped
        for label, field in buckets.items():
            prefix = f'{label}:'
            if stripped.lower().startswith(prefix):
                key = field
                rest = stripped[len(prefix):].strip()
                break
        if key:
            current = key
            if rest:
                collected[current].append(rest)
            continue
        if current:
            collected[current].append(stripped)
    return {
        'summary': ' '.join(collected['summary'])[:2000],
        'topics': _topics(collected['topics']),
        'problems': _strings(collected['problems']),
        'recommendations': _strings(collected['recommendations']),
    }


def _strings(value, limit=6):
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        text = str(item).strip() if not isinstance(item, dict) else ''
        if text:
            items.append(text[:300])
        if len(items) >= limit:
            break
    return items


def _topics(value, limit=6):
    if not isinstance(value, list):
        return []
    topics = []
    for item in value:
        if isinstance(item, str) and item.strip():
            title, _, detail = item.strip().partition('—')
            topics.append({
                'title': title.strip()[:120] or 'Тема',
                'detail': detail.strip()[:300],
            })
        elif isinstance(item, dict):
            title = str(item.get('title') or '').strip()[:120]
            detail = str(item.get('detail') or '').strip()[:300]
            if title or detail:
                topics.append({'title': title or 'Тема', 'detail': detail})
        if len(topics) >= limit:
            break
    return topics

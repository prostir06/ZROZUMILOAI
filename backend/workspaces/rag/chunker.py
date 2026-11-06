"""Розбиття тексту на фрагменти для RAG зі збереженням структури."""
import re

# Регулярні вирази для розрізу тексту за пріоритетами
SPLIT_PATTERNS = [
    re.compile(r'\n(?=#{1,6}\s)'),  # 1. Заголовок розділу
    re.compile(r'\n\s*\n+'),  # 2. Межа абзаців
    re.compile(r'\n(?=[ \t]*[-*\u2022]\s|[ \t]*\d+\.\s)'),  # 3. Елемент списку
    re.compile(r'\n'),  # 4. Перенесення рядка
    re.compile(r'(?<=[.!?])\s+'),  # 5. Межа речення
    re.compile(r'\s+'),  # 6. Межа слова
]

HEADING_REGEX = re.compile(r'^(#{1,6})\s+(.+)$')


def split_text_into_chunks(text, chunk_size=800, chunk_overlap=100):
    """
    Розбити текст на перекривні фрагменти зі збереженням контексту заголовків.

    Намагається ієрархічно різати за:
    1. Розділами markdown (# Заголовок)
    2. Абзацами
    3. Елементами списків (-, *, •, 1.)
    4. Рядками
    5. Реченнями
    6. Словами

    Зберігає ієрархію заголовків ([# Розділ > ## Підрозділ])
    у наступних фрагментах.
    """
    cleaned = text.strip()
    if not cleaned:
        return []

    if len(cleaned) <= chunk_size:
        return [cleaned]

    # Нормалізація параметрів
    chunk_overlap = max(0, min(chunk_overlap, chunk_size - 1))

    # Витягуємо заголовки та формуємо карту ієрархій
    headings = _extract_headings(cleaned)
    valid_heading_starts = {h['start'] for h in headings}

    chunks = []
    start = 0
    text_len = len(cleaned)

    while start < text_len:
        # Визначаємо, чи потрібен префікс контексту для поточного фрагмента
        current_slice = cleaned[start:]
        begins_with_heading = _begins_with_heading(current_slice)

        prefix = ''
        if not begins_with_heading:
            active_hierarchy = _get_active_hierarchy(headings, start)
            if active_hierarchy:
                prefix = f'{active_hierarchy} '

        # Доступний розмір для тексту самого фрагмента
        if prefix:
            target_size = max(chunk_size - len(prefix), 1)
        else:
            target_size = chunk_size

        end = min(start + target_size, text_len)
        is_major_section = False

        if end < text_len:
            split_at, is_major_section = _find_split_point(
                cleaned,
                start,
                end,
                chunk_overlap=chunk_overlap,
                valid_heading_starts=valid_heading_starts,
            )
            if split_at > start:
                end = split_at

        piece = cleaned[start:end].strip()
        if piece:
            chunk_content = f'{prefix}{piece}'
            # Захист від перевищення chunk_size при довгих словах чи префіксах
            if len(chunk_content) > chunk_size:
                chunk_content = chunk_content[:chunk_size]
            chunks.append(chunk_content)

        if end >= text_len:
            break

        # Якщо розріз відбувся на межі розділу, наступний фрагмент починається
        # точно із заголовка нового розділу (без перекриття з попереднього)
        if is_major_section:
            next_start = end
        else:
            next_start = max(end - chunk_overlap, start + 1)

        start = max(next_start, start + 1)

    return chunks


def _extract_headings(text):
    """
    Знайти markdown-заголовки поза межами блоків коду та побудувати ієрархію.

    Повертає список словників:
    [{'start': int, 'end': int, 'level': int, 'text': str, 'hierarchy': str}]
    """
    lines = text.splitlines(keepends=True)
    pos = 0
    in_code_block = False
    code_fence = None
    raw_headings = []

    for line in lines:
        line_stripped = line.strip()
        if line_stripped.startswith('```') or line_stripped.startswith('~~~'):
            fence = line_stripped[:3]
            if in_code_block and fence == code_fence:
                in_code_block = False
                code_fence = None
            elif not in_code_block:
                in_code_block = True
                code_fence = fence
        elif not in_code_block:
            match = HEADING_REGEX.match(line_stripped)
            if match:
                level = len(match.group(1))
                # Текст рядка заголовка (наприклад, '# Заголовок')
                heading_text = line_stripped
                raw_headings.append({
                    'start': pos,
                    'end': pos + len(line),
                    'level': level,
                    'text': heading_text,
                })
        pos += len(line)

    stack = []
    for h in raw_headings:
        while stack and stack[-1][0] >= h['level']:
            stack.pop()
        stack.append((h['level'], h['text']))
        h['hierarchy'] = f"[{' > '.join(item[1] for item in stack)}]"

    return raw_headings


def _get_active_hierarchy(headings, pos):
    """Отримати рядок активної ієрархії заголовків для позиції pos."""
    active = None
    for h in headings:
        if h['start'] <= pos:
            active = h['hierarchy']
        else:
            break
    return active


def _begins_with_heading(text_slice):
    """Перевірити, чи починається зріз тексту з markdown-заголовка."""
    return bool(re.match(r'^#{1,6}\s', text_slice.lstrip()))


def _find_split_point(
    text,
    start,
    end,
    chunk_overlap=0,
    valid_heading_starts=None,
):
    """
    Знайти найкращу точку розрізу в межах text[start:end].

    Повертає (split_at, is_major_section_break).
    """
    window = text[start:end]
    window_len = len(window)
    if not window:
        return end, False

    valid_heading_starts = valid_heading_starts or set()

    # Точка розрізу повинна робити поступ за межі overlap
    min_split = chunk_overlap if (
        start > 0 and chunk_overlap < window_len
    ) else 0

    for pattern_idx, pattern in enumerate(SPLIT_PATTERNS):
        matches = list(pattern.finditer(window))
        if not matches:
            continue

        if pattern_idx == 0:
            # Major section break: тільки якщо це валідний заголовок
            valid_matches = [
                m for m in matches
                if (start + m.end()) in valid_heading_starts
                and m.end() > min_split
            ]
            if valid_matches:
                return start + valid_matches[-1].end(), True
        else:
            valid_matches = [m for m in matches if m.end() > min_split]
            if valid_matches:
                return start + valid_matches[-1].end(), False

    return end, False

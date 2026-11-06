"""Unit-тести для структурного та семантичного розбиття тексту на фрагменти."""
from django.test import SimpleTestCase

from workspaces.rag.chunker import split_text_into_chunks


class StructuralChunkerTests(SimpleTestCase):
    def test_empty_and_whitespace(self):
        self.assertEqual(split_text_into_chunks(''), [])
        self.assertEqual(split_text_into_chunks('   '), [])
        self.assertEqual(split_text_into_chunks('\n\t  \n'), [])

    def test_short_text_single_chunk(self):
        text = 'Короткий текст без заголовків.'
        self.assertEqual(split_text_into_chunks(text, chunk_size=100), [text])

    def test_heading_context_preservation_single_level(self):
        text = (
            '# Заголовок\n\n'
            'Перший довгий абзац тексту, який містить пояснення концепції. '
            'Він детальний, щоб зайняти частину першого фрагмента.\n\n'
            'Другий довгий абзац тексту, який продовжує ту саму тему '
            'і не вміщується в один фрагмент разом із першим абзацом.\n\n'
            'Третій абзац тексту з додатковими висновками та підсумками.'
        )
        chunks = split_text_into_chunks(text, chunk_size=180, chunk_overlap=20)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(chunks[0].startswith('# Заголовок'))
        # Наступні фрагменти повинні мати префікс контексту активного заголовка
        for chunk in chunks[1:]:
            self.assertTrue(
                chunk.startswith('[# Заголовок] '),
                f'Фрагмент не містить префікса: {chunk[:40]}...',
            )
            self.assertLessEqual(len(chunk), 180)

    def test_heading_hierarchy_preservation_nested(self):
        text = (
            '# Розділ 1: Архітектура\n\n'
            '## Підрозділ 1.1: Сервісний шар\n\n'
            'Опис шару. Шар відповідає за бізнес-логіку, '
            'оркестрацію викликів зовнішніх моделей та збереження станів.\n\n'
            'Деталізація взаємодії сервісів з базою pgvector та '
            'повнотекстовим індексом Meilisearch для гібридного пошуку.'
        )
        chunks = split_text_into_chunks(text, chunk_size=200, chunk_overlap=20)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(chunks[0].startswith('# Розділ 1: Архітектура'))
        # Фрагменти після підрозділу повинні мати ієрархічний префікс
        subsequent_chunks = [c for c in chunks if not c.startswith('#')]
        self.assertTrue(len(subsequent_chunks) > 0)
        prefix = '[# Розділ 1: Архітектура > ## Підрозділ 1.1: Сервісний шар] '
        for chunk in subsequent_chunks:
            self.assertTrue(
                chunk.startswith(prefix),
                f'Очікувався ієрархічний префікс, отримано: {chunk[:60]}...',
            )
            self.assertLessEqual(len(chunk), 200)

    def test_heading_hierarchy_updates_on_new_section(self):
        text = (
            '# Вступ\n'
            'Короткий вступний блок.\n\n'
            '# Основна частина\n'
            'Довгий текст частини, який обов’язково розіб’ється '
            'на кілька окремих фрагментів через ліміт розміру.\n\n'
            'Продовження основної частини з розширеними прикладами.'
        )
        chunks = split_text_into_chunks(text, chunk_size=150, chunk_overlap=20)
        self.assertGreater(len(chunks), 2)
        part2_subsequent = [
            c for c in chunks
            if not c.startswith('#') and 'Основна частина' in c
        ]
        self.assertTrue(len(part2_subsequent) > 0)
        for chunk in part2_subsequent:
            self.assertTrue(chunk.startswith('[# Основна частина] '))
            self.assertNotIn('Вступ', chunk[:30])

    def test_splitting_on_list_items(self):
        text = (
            '# Перелік вимог\n'
            '- Пункт 1: Перша критична вимога до модулів безпеки\n'
            '- Пункт 2: Друга вимога щодо швидкодії векторного пошуку\n'
            '- Пункт 3: Третя вимога щодо сумісності зі стандартами'
        )
        chunks = split_text_into_chunks(text, chunk_size=90, chunk_overlap=0)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 90)
        list_chunks = [c for c in chunks if '- Пункт' in c]
        for c in list_chunks:
            self.assertTrue(
                c.startswith('- Пункт')
                or c.startswith('[# Перелік вимог] - Пункт')
                or c.startswith('# Перелік вимог\n- Пункт'),
                f'Неочікуваний початок фрагмента списку: {c[:40]}',
            )

    def test_splitting_on_paragraphs(self):
        p1 = 'Перший абзац з довільним змістом на шістдесят символів тут.'
        p2 = 'Другий абзац тексту аналогічного розміру для перевірки розрізу.'
        text = f'{p1}\n\n{p2}'
        chunks = split_text_into_chunks(text, chunk_size=80, chunk_overlap=0)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0], p1)
        self.assertEqual(chunks[1], p2)

    def test_respects_chunk_size_and_overlap(self):
        text = (
            'Перше речення тексту для тестування. '
            'Друге речення з додатковими словами. '
            'Третє речення продовжує розповідь. '
            'Четверте речення завершує перший блок. '
            'П’яте речення починає другий блок опису. '
            'Шосте речення деталізує властивості системи. '
            'Сьоме речення ставить крапку в цьому тесті.'
        )
        chunk_size = 120
        chunk_overlap = 30
        chunks = split_text_into_chunks(
            text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= chunk_size for c in chunks))

    def test_mixed_markdown_with_code_blocks(self):
        text = (
            '# Інструкція розробника\n\n'
            'Ось приклад функції на Python:\n\n'
            '```python\n'
            '# це коментар усередині блоку коду, а не заголовок markdown\n'
            'def calculate_total(items):\n'
            '    return sum(items)\n'
            '```\n\n'
            'Після блоку коду наведено докладне пояснення логіки роботи, '
            'яке продовжує інструкцію розробника і демонструє параметри.'
        )
        chunks = split_text_into_chunks(text, chunk_size=180, chunk_overlap=20)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertNotIn('[# це коментар', chunk)
            self.assertLessEqual(len(chunk), 180)

    def test_oversized_single_word_clamps(self):
        long_word = 'НадзвичайноДовгеСловоБезПробілів' * 10
        chunks = split_text_into_chunks(
            long_word,
            chunk_size=50,
            chunk_overlap=10,
        )
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= 50 for c in chunks))

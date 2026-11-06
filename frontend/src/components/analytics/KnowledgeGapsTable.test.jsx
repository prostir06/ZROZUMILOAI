import React from 'react';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import KnowledgeGapsTable from './KnowledgeGapsTable';

describe('KnowledgeGapsTable component', () => {
  it('renders table with prompt, reason badges, response snippet, and action button', () => {
    const mockGaps = [
      {
        id: 1,
        created_at: '2026-11-06T12:00:00Z',
        prompt: 'Як отримати сертифікат після курсу?',
        response_snippet: 'На жаль, у наданих матеріалах немає точної інформації.',
        needs_handoff: true,
        feedback: null,
        reason: 'low_confidence',
      },
      {
        id: 2,
        created_at: '2026-11-06T13:30:00Z',
        prompt: 'Які дедлайни другого модуля?',
        response_snippet: 'Дедлайн 15 числа.',
        needs_handoff: false,
        feedback: 'down',
        reason: 'negative_feedback',
      },
    ];

    const html = renderToString(
      <KnowledgeGapsTable gaps={mockGaps} onUploadClick={() => {}} />,
    );

    // Table container and headers
    expect(html).toContain('knowledge-gaps-table');
    expect(html).toContain('Дата');
    expect(html).toContain('Питання');
    expect(html).toContain('Причина');
    expect(html).toContain('Відповідь ШІ');
    expect(html).toContain('Дія');

    // Row contents & prompts
    expect(html).toContain('Як отримати сертифікат після курсу?');
    expect(html).toContain('Які дедлайни другого модуля?');

    // Reason badges
    expect(html).toContain('Низька впевненість RAG');
    expect(html).toContain('gap-badge--low-confidence');
    expect(html).toContain('Негативна оцінка');
    expect(html).toContain('gap-badge--negative-feedback');

    // AI preview snippets
    expect(html).toContain('На жаль, у наданих матеріалах немає точної інформації.');
    expect(html).toContain('Дедлайн 15 числа.');

    // Action button
    expect(html).toContain('Додати матеріал');
  });

  it('renders empty state message when gaps is empty', () => {
    const html = renderToString(<KnowledgeGapsTable gaps={[]} />);

    expect(html).toContain(
      'Прогалин не виявлено. Всі запитання мають високу впевненість та позитивні оцінки.',
    );
    expect(html).not.toContain('<tbody>');
  });

  it('renders safely without crashing when gaps is null or undefined', () => {
    const htmlNull = renderToString(<KnowledgeGapsTable gaps={null} />);
    expect(htmlNull).toContain(
      'Прогалин не виявлено. Всі запитання мають високу впевненість та позитивні оцінки.',
    );

    const htmlUndefined = renderToString(<KnowledgeGapsTable />);
    expect(htmlUndefined).toContain(
      'Прогалин не виявлено. Всі запитання мають високу впевненість та позитивні оцінки.',
    );
  });
});

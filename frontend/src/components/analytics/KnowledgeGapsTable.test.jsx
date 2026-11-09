import React from 'react';
import { renderToString } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import KnowledgeGapsTable from './KnowledgeGapsTable';

function findButtons(element) {
  const buttons = [];
  function traverse(node) {
    if (!node || typeof node !== 'object') return;
    if (node.type === 'button') buttons.push(node);
    if (Array.isArray(node.props?.children)) {
      node.props.children.forEach(traverse);
    } else if (node.props?.children) {
      traverse(node.props.children);
    }
  }
  traverse(element);
  return buttons;
}

describe('KnowledgeGapsTable component', () => {
  const mockGaps = [
    {
      id: 1,
      created_at: '2026-11-06T12:00:00Z',
      prompt: 'Як отримати сертифікат після курсу?',
      response_snippet: 'На жаль, у наданих матеріалах немає точної інформації.',
      needs_handoff: true,
      feedback: null,
      reason: 'low_confidence',
      is_resolved: false,
    },
    {
      id: 2,
      created_at: '2026-11-06T13:30:00Z',
      prompt: 'Які дедлайни другого модуля?',
      response_snippet: 'Дедлайн 15 числа.',
      needs_handoff: false,
      feedback: 'down',
      reason: 'negative_feedback',
      is_resolved: true,
    },
  ];

  it('renders table with prompt, reason badges, response snippet, and action button', () => {
    const html = renderToString(
      <KnowledgeGapsTable gaps={mockGaps} onUploadClick={() => {}} />,
    );

    // Table container and headers
    expect(html).toContain('knowledge-gaps-table');
    expect(html).toContain('Дата');
    expect(html).toContain('Питання');
    expect(html).toContain('Причина');
    expect(html).toContain('Статус');
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

  it('displays resolution badges and buttons for open and resolved gaps', () => {
    const html = renderToString(
      <KnowledgeGapsTable gaps={mockGaps} onResolveClick={() => {}} />,
    );

    // Badges
    expect(html).toContain('Потребує матеріалу');
    expect(html).toContain('gap-badge--pending');
    expect(html).toContain('Вирішено');
    expect(html).toContain('gap-badge--resolved');

    // Action buttons
    expect(html).toContain('✓ Вирішено');
    expect(html).toContain('↩ Відкрити');
  });

  it('renders filter tabs and displays counts', () => {
    const html = renderToString(
      <KnowledgeGapsTable gaps={mockGaps} />,
    );

    expect(html).toContain('knowledge-gaps-filters');
    expect(html).toContain('Всі (2)');
    expect(html).toContain('Відкриті (1)');
    expect(html).toContain('Вирішені (1)');
  });

  it('triggers onResolveClick with gap and target resolution status', () => {
    const onResolveClick = vi.fn();
    let tree;
    function Wrapper() {
      tree = KnowledgeGapsTable({
        gaps: mockGaps,
        onResolveClick,
      });
      return tree;
    }
    renderToString(<Wrapper />);

    const buttons = findButtons(tree);
    const resolveBtn = buttons.find((btn) =>
      typeof btn.props?.children === 'string'
        ? btn.props.children.includes('✓ Вирішено')
        : Array.isArray(btn.props?.children) && btn.props.children.some((c) => String(c).includes('✓ Вирішено')),
    );
    const reopenBtn = buttons.find((btn) =>
      typeof btn.props?.children === 'string'
        ? btn.props.children.includes('↩ Відкрити')
        : Array.isArray(btn.props?.children) && btn.props.children.some((c) => String(c).includes('↩ Відкрити')),
    );

    expect(resolveBtn).toBeDefined();
    expect(reopenBtn).toBeDefined();

    resolveBtn.props.onClick();
    expect(onResolveClick).toHaveBeenCalledWith(mockGaps[0], true);

    reopenBtn.props.onClick();
    expect(onResolveClick).toHaveBeenCalledWith(mockGaps[1], false);
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

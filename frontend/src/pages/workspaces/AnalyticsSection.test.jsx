import React from 'react';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import AnalyticsSection from './AnalyticsSection';

describe('AnalyticsSection component', () => {
  it('renders range controls and export button', () => {
    const html = renderToString(
      <AnalyticsSection
        workspaceId={42}
        initialAnalytics={{
          total_queries: 10,
          unique_users: 2,
          csat_score: 100,
          feedback_up: 5,
          feedback_down: 0,
          handoff_rate: 0,
          handoff_count: 0,
          knowledge_gaps: [],
        }}
      />,
    );

    // Range buttons
    expect(html).toContain('Сьогодні');
    expect(html).toContain('7 днів');
    expect(html).toContain('30 днів');
    expect(html).toContain('Весь час');

    // Export button
    expect(html).toContain('Експорт CSV');

    // Section title
    expect(html).toContain('Аналітика та прогалини знань');
    expect(html).toContain('Черга прогалин знань (Knowledge Gaps)');
  });

  it('renders KpiCards and KnowledgeGapsTable with provided data', () => {
    const mockAnalytics = {
      total_queries: 50,
      unique_users: 12,
      csat_score: 80,
      feedback_up: 8,
      feedback_down: 2,
      handoff_rate: 10,
      handoff_count: 5,
      knowledge_gaps: [
        {
          id: 101,
          created_at: '2026-11-06T10:00:00Z',
          prompt: 'Як подати апеляцію?',
          response_snippet: 'Немає інформації про апеляцію.',
          needs_handoff: true,
          feedback: null,
          reason: 'low_confidence',
        },
      ],
    };

    const html = renderToString(
      <AnalyticsSection workspaceId={1} initialAnalytics={mockAnalytics} />,
    );

    expect(html).toContain('50');
    expect(html).toContain('12');
    expect(html).toContain('80%');
    expect(html).toContain('Як подати апеляцію?');
    expect(html).toContain('Низька впевненість RAG');
    expect(html).toContain('Додати матеріал');
  });
});

import React from 'react';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import KpiCards from './KpiCards';

describe('KpiCards component', () => {
  it('renders total queries, unique users, CSAT %, up/down counters, handoff rate %, and knowledge gaps count when populated', () => {
    const mockAnalytics = {
      total_queries: 1250,
      unique_users: 85,
      csat_score: 94.5,
      feedback_up: 189,
      feedback_down: 11,
      handoff_rate: 6.2,
      handoff_count: 78,
      knowledge_gaps: [
        { id: 1, prompt: 'Як зареєструватись на курс?' },
        { id: 2, prompt: 'Де знайти сертифікат?' },
      ],
    };

    const html = renderToString(<KpiCards analytics={mockAnalytics} />);

    // Container
    expect(html).toContain('kpi-grid');

    // Total queries & unique users
    expect(html).toContain('Всього запитів');
    expect(html).toContain('1250');
    expect(html).toContain('85');

    // CSAT & feedback
    expect(html).toContain('Індекс корисності');
    expect(html).toContain('94.5%');
    expect(html).toContain('189');
    expect(html).toContain('11');

    // Handoff rate & count
    expect(html).toContain('Рівень ескалації');
    expect(html).toContain('6.2%');
    expect(html).toContain('78');

    // Knowledge gaps
    expect(html).toContain('Прогалини знань');
    expect(html).toContain('2');
  });

  it('handles empty / zero state data safely without NaN or crashing', () => {
    const zeroAnalytics = {
      total_queries: 0,
      unique_users: 0,
      csat_score: 0,
      feedback_up: 0,
      feedback_down: 0,
      handoff_rate: 0,
      handoff_count: 0,
      knowledge_gaps: [],
    };

    const html = renderToString(<KpiCards analytics={zeroAnalytics} />);

    expect(html).toContain('kpi-grid');
    expect(html).not.toContain('NaN');
    expect(html).toContain('Всього запитів');
    expect(html).toContain('0%');
    expect(html).toContain('Індекс корисності');
    expect(html).toContain('Рівень ескалації');
    expect(html).toContain('Прогалини знань');
  });

  it('renders graceful zero values or skeleton fallback when analytics prop is missing or undefined', () => {
    const htmlUndefined = renderToString(<KpiCards />);
    expect(htmlUndefined).toContain('kpi-grid');
    expect(htmlUndefined).not.toContain('NaN');
    expect(htmlUndefined).toContain('Всього запитів');
    expect(htmlUndefined).toContain('0');

    const htmlNull = renderToString(<KpiCards analytics={null} />);
    expect(htmlNull).toContain('kpi-grid');
    expect(htmlNull).not.toContain('NaN');
    expect(htmlNull).toContain('Всього запитів');
  });
});

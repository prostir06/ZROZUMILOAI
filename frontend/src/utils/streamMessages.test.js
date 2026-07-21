import { describe, expect, it } from 'vitest';

import { applyStreamChunk } from './streamMessages.js';

describe('applyStreamChunk', () => {
  const base = [
    { role: 'user', content: 'Hi' },
    { role: 'assistant', content: '' },
  ];

  it('додає текст відповіді', () => {
    const next = applyStreamChunk(base, {
      message: { content: 'Привіт' },
    });
    expect(next[1].content).toBe('Привіт');
  });

  it('зберігає sources і log_id', () => {
    let next = applyStreamChunk(base, {
      sources: [{ document_name: 'FAQ', score: 0.8, excerpt: '…' }],
    });
    next = applyStreamChunk(next, { log_id: 7, needs_handoff: true });
    expect(next[1].sources).toHaveLength(1);
    expect(next[1].logId).toBe(7);
    expect(next[1].needsHandoff).toBe(true);
  });

  it('не змінює messages без assistant', () => {
    const onlyUser = [{ role: 'user', content: 'x' }];
    expect(applyStreamChunk(onlyUser, { message: { content: 'y' } })).toBe(onlyUser);
  });

  it('повертає messages для null/порожнього chunk', () => {
    expect(applyStreamChunk(null, { message: { content: 'x' } })).toBe(null);
    expect(applyStreamChunk(base, null)).toBe(base);
    expect(applyStreamChunk(base, {})).toBe(base);
  });

  it('metaOnly не дублює content', () => {
    const withText = [
      { role: 'user', content: 'Hi' },
      { role: 'assistant', content: 'Вже є' },
    ];
    const next = applyStreamChunk(
      withText,
      {
        message: { content: ' дубль' },
        sources: [{ document_name: 'A', score: 1, excerpt: '' }],
        log_id: 3,
      },
      { metaOnly: true },
    );
    expect(next[1].content).toBe('Вже є');
    expect(next[1].sources).toHaveLength(1);
    expect(next[1].logId).toBe(3);
  });

  it('записує error у content', () => {
    const next = applyStreamChunk(base, { error: 'timeout' });
    expect(next[1].content).toBe('Помилка: timeout');
  });

  it('дозволяє needs_handoff: false', () => {
    const next = applyStreamChunk(base, { needs_handoff: false });
    expect(next[1].needsHandoff).toBe(false);
  });
});

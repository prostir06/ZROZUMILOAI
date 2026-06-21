import { describe, expect, it } from 'vitest';

import { buildChatTitle, formatChatDate } from './chat.js';

describe('buildChatTitle', () => {
  it('повертає дефолт для порожнього тексту', () => {
    expect(buildChatTitle('')).toBe('Новий чат');
    expect(buildChatTitle('   ')).toBe('Новий чат');
  });

  it('обрізає довгий текст до 60 символів', () => {
    const long = 'а'.repeat(70);
    expect(buildChatTitle(long)).toBe(`${'а'.repeat(60)}…`);
  });

  it('залишає короткий текст без змін', () => {
    expect(buildChatTitle('Привіт')).toBe('Привіт');
  });
});

describe('formatChatDate', () => {
  it('повертає порожній рядок для невалідної дати', () => {
    expect(formatChatDate('')).toBe('');
    expect(formatChatDate('not-a-date')).toBe('');
  });

  it('форматує ISO-дату без помилки', () => {
    const result = formatChatDate('2024-06-15T10:30:00.000Z');
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
  });
});

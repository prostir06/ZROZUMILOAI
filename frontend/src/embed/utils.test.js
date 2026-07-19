import { describe, expect, it } from 'vitest';

import {
  buildAuthHeader,
  EMBED_FAQ_QUESTIONS,
  escapeHtml,
  formatBoldTextHtml,
  formatMessageContent,
  getEmbedStatusText,
  sanitizeColor,
  sanitizeTitle,
  truncateText,
} from './utils.js';

describe('escapeHtml', () => {
  it('екранує спецсимволи HTML', () => {
    expect(escapeHtml('<script>&')).toBe('&lt;script&gt;&amp;');
  });

  it('повертає порожній рядок для null', () => {
    expect(escapeHtml(null)).toBe('');
  });
});

describe('formatBoldTextHtml', () => {
  it('перетворює **текст** на strong', () => {
    expect(formatBoldTextHtml('**Привіт**')).toBe('<strong>Привіт</strong>');
  });

  it('екранує HTML у bold-сегментах', () => {
    expect(formatBoldTextHtml('**<x>**')).toBe('<strong>&lt;x&gt;</strong>');
  });
});

describe('formatMessageContent', () => {
  it('assistant — з bold', () => {
    expect(formatMessageContent('**Hi**', 'assistant')).toContain('<strong>');
  });

  it('user — лише escape', () => {
    expect(formatMessageContent('<b>', 'user')).toBe('&lt;b&gt;');
  });
});

describe('truncateText', () => {
  it('скорочує довгий текст', () => {
    expect(truncateText('abcdefgh', 5)).toBe('abcde…');
  });

  it('повертає — для порожнього', () => {
    expect(truncateText('', 10)).toBe('—');
  });
});

describe('buildAuthHeader', () => {
  it('widget token', () => {
    expect(buildAuthHeader({ widgetToken: 'wt_abc' })).toBe('Widget-Token wt_abc');
  });

  it('api key', () => {
    expect(buildAuthHeader({ apiKey: 'zai_key' })).toBe('Api-Key zai_key');
  });

  it('без config — порожній рядок', () => {
    expect(buildAuthHeader(null)).toBe('');
  });
});

describe('getEmbedStatusText', () => {
  it('немає workspace з widget token', () => {
    const text = getEmbedStatusText({ widgetToken: 'wt_x' }, null, '');
    expect(text).toContain('Widget token');
  });

  it('є model', () => {
    expect(getEmbedStatusText({}, { name: 'ws' }, 'llama3')).toBe('Модель: llama3');
  });

  it('initError має пріоритет', () => {
    expect(getEmbedStatusText({}, null, '', 'Custom error')).toBe('Custom error');
  });
});

describe('sanitizeColor', () => {
  it('приймає валідний hex', () => {
    expect(sanitizeColor('#0D9E96')).toBe('#0D9E96');
  });

  it('відхиляє небезпечні значення', () => {
    expect(sanitizeColor('red; background:url(x)')).toBe('#0D9E96');
  });
});

describe('sanitizeTitle', () => {
  it('прибирає HTML-символи', () => {
    expect(sanitizeTitle('<script>')).toBe('script');
  });

  it('повертає значення за замовчуванням', () => {
    expect(sanitizeTitle('')).toBe('Підтримка');
  });
});

describe('EMBED_FAQ_QUESTIONS', () => {
  it('містить три часті запитання', () => {
    expect(EMBED_FAQ_QUESTIONS).toHaveLength(3);
    expect(EMBED_FAQ_QUESTIONS[0]).toBe('Як зареєструватися?');
  });
});

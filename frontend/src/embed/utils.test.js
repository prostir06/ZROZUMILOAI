import { describe, expect, it, vi } from 'vitest';

import {
  buildAuthHeader,
  EMBED_FAQ_QUESTIONS,
  escapeHtml,
  formatBoldTextHtml,
  formatMessageContent,
  getEmbedStatusText,
  isIso88591,
  readEmbedFeedbackClick,
  safeJson,
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

describe('isIso88591', () => {
  it('повертає true для ASCII рядків', () => {
    expect(isIso88591('wt_abc-123_XYZ')).toBe(true);
    expect(isIso88591('Authorization: Bearer token')).toBe(true);
  });

  it('повертає false для кирилиці та символів > 255', () => {
    expect(isIso88591('wt_ВАШ_TOKEN')).toBe(false);
    expect(isIso88591('Підтримка')).toBe(false);
    expect(isIso88591('👋')).toBe(false);
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

  it('відхиляє не-ISO-8859-1 токени (наприклад кириличні плейсхолдери)', () => {
    expect(buildAuthHeader({ widgetToken: 'wt_ВАШ_TOKEN' })).toBe('');
    expect(buildAuthHeader({ apiKey: 'ключ' })).toBe('');
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

  it('екранує HTML у model', () => {
    expect(getEmbedStatusText({}, { name: 'ws' }, '<img src=x>')).toBe(
      'Модель: &lt;img src=x&gt;',
    );
  });

  it('initError має пріоритет', () => {
    expect(getEmbedStatusText({}, null, '', 'Custom error')).toBe('Custom error');
  });

  it('екранує HTML у initError', () => {
    expect(getEmbedStatusText({}, null, '', '<b>fail</b>')).toBe('&lt;b&gt;fail&lt;/b&gt;');
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

describe('safeJson', () => {
  it('логає зіпсований JSON і повертає fallback', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const response = {
      json: async () => {
        throw new Error('bad json');
      },
    };

    await expect(safeJson(response, { error: 'fallback' })).resolves.toEqual({
      error: 'fallback',
    });
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });
});

describe('readEmbedFeedbackClick', () => {
  function button(attrs) {
    return {
      hasAttribute: (name) => Object.prototype.hasOwnProperty.call(attrs, name),
      getAttribute: (name) => attrs[name] ?? null,
      closest: () => button(attrs),
    };
  }

  function block(logId) {
    return { getAttribute: () => logId };
  }

  it('читає оцінку вниз', () => {
    expect(readEmbedFeedbackClick(button({ 'data-feedback': 'down' }), block('12')))
      .toEqual({ logId: 12, payload: { feedback: 'down' } });
  });

  it('читає запит людини', () => {
    expect(readEmbedFeedbackClick(button({ 'data-handoff': '1' }), block('4')))
      .toEqual({ logId: 4, payload: { needs_handoff: true } });
  });

  it('ігнорує клік без log id', () => {
    expect(readEmbedFeedbackClick(button({ 'data-feedback': 'up' }), block(''))).toBeNull();
  });
});

describe('EMBED_FAQ_QUESTIONS', () => {
  it('містить три часті запитання', () => {
    expect(EMBED_FAQ_QUESTIONS).toHaveLength(3);
    expect(EMBED_FAQ_QUESTIONS[0]).toBe('Як зареєструватися?');
  });
});

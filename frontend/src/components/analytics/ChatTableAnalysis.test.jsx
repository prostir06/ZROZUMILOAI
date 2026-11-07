import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import ChatTableAnalysis from './ChatTableAnalysis';

describe('ChatTableAnalysis', () => {
  it('показує висновок локальної моделі і лічильники таблиці', () => {
    const html = renderToString(
      <ChatTableAnalysis
        analysis={{
          model: 'qwen3:latest',
          total: 11,
          handoff: 2,
          feedback_up: 4,
          feedback_down: 1,
          summary: 'Найчастіше питають про сертифікат.',
          topics: [{ title: 'Сертифікат', detail: 'Кілька схожих запитів' }],
          problems: ['Мало оцінок'],
          recommendations: ['Додати коротку відповідь у FAQ'],
        }}
      />,
    );

    expect(html).toContain('Локальна модель: qwen3:latest');
    expect(html).toContain('Найчастіше питають про сертифікат.');
    expect(html).toContain('Сертифікат');
    expect(html).toContain('Додати коротку відповідь у FAQ');
    expect(html).toContain('>11<');
  });
});

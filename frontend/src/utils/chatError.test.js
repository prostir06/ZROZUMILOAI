import { describe, expect, it } from 'vitest';
import { formatChatError } from './chatError';

describe('formatChatError', () => {
  it('показує ollama_busy без префікса Помилка', () => {
    expect(formatChatError({
      code: 'ollama_busy',
      message: 'Модель зайнята. Спробуйте ще раз за хвилину.',
    })).toBe('Модель зайнята. Спробуйте ще раз за хвилину.');
  });

  it('підставляє текст за замовчуванням, якщо повідомлення порожнє', () => {
    expect(formatChatError({ code: 'ollama_busy', message: '' }))
      .toBe('Модель зайнята. Спробуйте ще раз за хвилину.');
  });

  it('інші помилки лишає з префіксом', () => {
    expect(formatChatError({ message: 'немає мережі' })).toBe('Помилка: немає мережі');
  });
});

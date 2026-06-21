import { describe, expect, it } from 'vitest';

import {
  isModelInstalled,
  REQUIRED_CHAT_MODEL,
  REQUIRED_RAG_MODEL,
  shouldShowRequiredModels,
} from './models.js';

describe('isModelInstalled', () => {
  it('знаходить модель з тегом :latest', () => {
    const models = [{ name: 'gemma3:latest' }];
    expect(isModelInstalled(models, 'gemma3')).toBe(true);
  });

  it('повертає false якщо моделі немає', () => {
    expect(isModelInstalled([{ name: 'llama3.2:latest' }], 'gemma3')).toBe(false);
  });
});

describe('shouldShowRequiredModels', () => {
  it('ховає блок коли обидві моделі встановлені', () => {
    const models = [
      { name: `${REQUIRED_CHAT_MODEL}:latest` },
      { name: `${REQUIRED_RAG_MODEL}:latest` },
    ];
    expect(shouldShowRequiredModels(models)).toBe(false);
  });

  it('показує блок якщо бракує RAG-моделі', () => {
    const models = [{ name: `${REQUIRED_CHAT_MODEL}:latest` }];
    expect(shouldShowRequiredModels(models)).toBe(true);
  });
});

/** Моделі Ollama, обовʼязкові для роботи платформи. */
export const REQUIRED_CHAT_MODEL = 'gemma3';
export const REQUIRED_RAG_MODEL = 'nomic-embed-text';

/**
 * Чи встановлена модель у Ollama (порівняння без тегу :latest).
 * @param {Array<{ name: string }>} modelList
 * @param {string} baseName
 */
export function isModelInstalled(modelList, baseName) {
  return modelList.some((model) => model.name.split(':')[0] === baseName);
}

/**
 * Чи потрібно показувати блок «Необхідні для роботи».
 * @param {Array<{ name: string }>} modelList
 */
export function shouldShowRequiredModels(modelList) {
  return (
    !isModelInstalled(modelList, REQUIRED_CHAT_MODEL)
    || !isModelInstalled(modelList, REQUIRED_RAG_MODEL)
  );
}

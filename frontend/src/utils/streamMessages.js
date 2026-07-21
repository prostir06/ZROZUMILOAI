/**
 * Застосувати SSE-чанк до списку повідомлень чату (sources / content / meta).
 *
 * ChatPage застосовує текст через rAF (patchLastAssistant), а meta
 * (sources / logId / needsHandoff) — через applyStreamChunk з metaOnly,
 * щоб уникнути подвійного append content.
 */

/**
 * Оновити останнє assistant-повідомлення з полями стріму.
 *
 * @param {Array} messages
 * @param {object} chunk
 * @param {{ metaOnly?: boolean }} [options] — якщо true, ігнорує message.content
 *   (контент уже додано окремим шляхом).
 * @returns {Array}
 */
export function applyStreamChunk(messages, chunk, options = {}) {
  if (!Array.isArray(messages) || !messages.length || !chunk || typeof chunk !== 'object') {
    return messages;
  }

  const lastIndex = messages.length - 1;
  const last = messages[lastIndex];
  if (last.role !== 'assistant') {
    return messages;
  }

  const metaOnly = Boolean(options.metaOnly);
  let next = last;
  let changed = false;

  if (Array.isArray(chunk.sources)) {
    next = { ...next, sources: chunk.sources };
    changed = true;
  }

  if (chunk.log_id != null) {
    next = { ...next, logId: chunk.log_id };
    changed = true;
  }

  if (typeof chunk.needs_handoff === 'boolean') {
    next = { ...next, needsHandoff: chunk.needs_handoff };
    changed = true;
  }

  if (!metaOnly) {
    if (chunk.error) {
      next = { ...next, content: `Помилка: ${chunk.error}` };
      changed = true;
    } else if (chunk.message?.content) {
      next = { ...next, content: (next.content || '') + chunk.message.content };
      changed = true;
    }
  }

  if (!changed) {
    return messages;
  }

  return [...messages.slice(0, lastIndex), next];
}

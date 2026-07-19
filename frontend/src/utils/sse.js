/**
 * Спільний парсер Server-Sent Events (SSE) для chat/pull streaming.
 * Використовується ApiClient та може бути перевикористаний у embed.
 */

/**
 * Читати ReadableStream відповіді як SSE data: рядки.
 * @param {Response} response
 * @param {(data: object) => void} onChunk
 * @param {{ signal?: AbortSignal }} [options]
 */
export async function consumeSSE(response, onChunk, options = {}) {
  if (!response.body) {
    throw new Error('Порожня відповідь сервера');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const signal = options.signal;

  const abort = () => {
    try {
      reader.cancel();
    } catch {
      /* ignore */
    }
  };

  if (signal) {
    if (signal.aborted) {
      abort();
      throw new DOMException('Aborted', 'AbortError');
    }
    signal.addEventListener('abort', abort, { once: true });
  }

  try {
    let doneReading = false;
    while (!doneReading) {
      if (signal?.aborted) {
        throw new DOMException('Aborted', 'AbortError');
      }
      const { done, value } = await reader.read();
      doneReading = done;
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) {
          continue;
        }
        try {
          const data = JSON.parse(line.slice(6));
          onChunk(data);
        } catch {
          /* пропускаємо пошкоджені SSE-чанки */
        }
      }
    }
  } finally {
    if (signal) {
      signal.removeEventListener('abort', abort);
    }
  }
}

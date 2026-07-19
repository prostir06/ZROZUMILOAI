import { describe, expect, it, vi } from 'vitest';

import { consumeSSE } from './sse.js';

function makeResponse(chunks) {
  let index = 0;
  const encoder = new TextEncoder();
  return {
    body: {
      getReader() {
        return {
          async read() {
            if (index >= chunks.length) {
              return { done: true, value: undefined };
            }
            const value = encoder.encode(chunks[index]);
            index += 1;
            return { done: false, value };
          },
          cancel: vi.fn(),
        };
      },
    },
  };
}

describe('consumeSSE', () => {
  it('парсить data: рядки', async () => {
    const received = [];
    const response = makeResponse([
      'data: {"message":{"content":"Hi"}}\n\n',
      'data: {"done":true}\n\n',
    ]);
    await consumeSSE(response, (chunk) => received.push(chunk));
    expect(received).toHaveLength(2);
    expect(received[0].message.content).toBe('Hi');
  });

  it('ігнорує биті JSON', async () => {
    const received = [];
    const response = makeResponse(['data: {not-json}\n\n', 'data: {"ok":1}\n\n']);
    await consumeSSE(response, (chunk) => received.push(chunk));
    expect(received).toEqual([{ ok: 1 }]);
  });
});

import { describe, expect, it } from 'vitest';

import { safeJson } from './safeJson.js';

describe('safeJson', () => {
  it('повертає розпарсений JSON', async () => {
    const response = new Response(JSON.stringify({ ok: true }), {
      headers: { 'Content-Type': 'application/json' },
    });
    await expect(safeJson(response)).resolves.toEqual({ ok: true });
  });

  it('повертає fallback для невалідного JSON', async () => {
    const response = new Response('not json', {
      headers: { 'Content-Type': 'text/plain' },
    });
    await expect(safeJson(response, {})).resolves.toEqual({});
  });
});

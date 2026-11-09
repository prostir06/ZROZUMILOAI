import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { BaseApiClient } from './base';

describe('ApiBase error resilience', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('getAuthConfig returns fallback config when fetch throws network error', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));

    const api = new BaseApiClient();
    const config = await api.getAuthConfig();

    expect(config).toEqual({ allow_registration: true });
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/auth/config/');
  });

  it('getAuthConfig returns fallback config when response is not ok', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
    });

    const api = new BaseApiClient();
    const config = await api.getAuthConfig();

    expect(config).toEqual({ allow_registration: true });
  });

  it('getAuthConfig returns parsed JSON when response is ok', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ allow_registration: false, default_model: 'llama3' }),
    });

    const api = new BaseApiClient();
    const config = await api.getAuthConfig();

    expect(config).toEqual({ allow_registration: false, default_model: 'llama3' });
  });
});

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { BaseApiClient } from './base';

describe('ApiBase error resilience', () => {
  const originalFetch = globalThis.fetch;
  const originalLocalStorage = globalThis.localStorage;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    if (originalLocalStorage === undefined) {
      delete globalThis.localStorage;
    } else {
      globalThis.localStorage = originalLocalStorage;
    }
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

  it('refreshToken saves rotated refresh token and deduplicates concurrent calls', async () => {
    const storage = new Map([['refresh_token', 'old-refresh']]);
    globalThis.localStorage = {
      getItem: (k) => storage.get(k) ?? null,
      setItem: (k, v) => storage.set(k, String(v)),
      removeItem: (k) => storage.delete(k),
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ access: 'new-access', refresh: 'new-refresh' }),
    });

    const api = new BaseApiClient();
    const [ok1, ok2] = await Promise.all([api.refreshToken(), api.refreshToken()]);

    expect(ok1).toBe(true);
    expect(ok2).toBe(true);
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    expect(storage.get('access_token')).toBe('new-access');
    expect(storage.get('refresh_token')).toBe('new-refresh');
  });

  it('deleteUser and updateUser throw clean fallback errors on non-JSON error responses', async () => {
    globalThis.localStorage = {
      getItem: () => null,
      setItem: () => {},
      removeItem: () => {},
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      json: async () => {
        throw new SyntaxError('Unexpected token < in JSON');
      },
    });

    const api = new BaseApiClient();
    await expect(api.deleteUser(5)).rejects.toThrow('Не вдалося видалити користувача');
    await expect(api.updateUser(5, { is_staff: false })).rejects.toThrow('Не вдалося оновити користувача');
  });
});

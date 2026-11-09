import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { ApiClient } from './client';

describe('ApiClient resolveKnowledgeGap', () => {
  let client;
  let originalFetch;
  let originalLocalStorage;

  beforeEach(() => {
    client = new ApiClient();
    originalFetch = globalThis.fetch;
    originalLocalStorage = globalThis.localStorage;
    globalThis.localStorage = {
      getItem: vi.fn().mockReturnValue('mock-token'),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    };
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    globalThis.localStorage = originalLocalStorage;
    vi.restoreAllMocks();
  });

  it('sends PATCH request to resolve endpoint with default resolved = true', async () => {
    const mockResponse = {
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({
        success: true,
        log_id: 42,
        is_resolved: true,
        resolved_at: '2026-11-09T17:00:00Z',
      }),
    };
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse);

    const result = await client.resolveKnowledgeGap(1, 42);

    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    const [url, options] = globalThis.fetch.mock.calls[0];
    expect(url).toBe('/api/workspaces/1/analytics/gaps/42/resolve/');
    expect(options.method).toBe('PATCH');
    expect(JSON.parse(options.body)).toEqual({ resolved: true });
    expect(result.success).toBe(true);
    expect(result.is_resolved).toBe(true);
  });

  it('sends PATCH request with resolved = false to reopen gap', async () => {
    const mockResponse = {
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({
        success: true,
        log_id: 42,
        is_resolved: false,
        resolved_at: null,
      }),
    };
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse);

    const result = await client.resolveKnowledgeGap(1, 42, false);

    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    const [, options] = globalThis.fetch.mock.calls[0];
    expect(options.method).toBe('PATCH');
    expect(JSON.parse(options.body)).toEqual({ resolved: false });
    expect(result.is_resolved).toBe(false);
  });

  it('throws descriptive error on failed response', async () => {
    const mockResponse = {
      ok: false,
      status: 404,
      json: vi.fn().mockResolvedValue({ error: 'Прогалину знань не знайдено' }),
    };
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse);

    await expect(client.resolveKnowledgeGap(1, 999)).rejects.toThrow(
      'Прогалину знань не знайдено',
    );
  });
});

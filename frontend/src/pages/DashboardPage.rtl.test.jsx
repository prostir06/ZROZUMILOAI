// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import * as AuthContextModule from '../context/AuthContext';
import DashboardPage from './DashboardPage';

describe('DashboardPage observability cards', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: { username: 'admin', first_name: 'Олена', is_staff: true },
    });
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'ok', database: 'ok', cache: 'ok' }),
    });
    vi.spyOn(api, 'getOllamaHealth').mockResolvedValue({
      connected: true,
      base_url: 'http://ollama:11434',
    });
    vi.spyOn(api, 'getModels').mockResolvedValue({ models: [] });
    vi.spyOn(api, 'getWorkspaceChatLogs').mockResolvedValue({ count: 3, results: [] });
  });

  afterEach(() => {
    cleanup();
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('renders healthy Celery, Telegram Poller, and RAG cards from getSystemHealthDetails', async () => {
    vi.spyOn(api, 'getSystemHealthDetails').mockResolvedValue({
      status: 'ok',
      celery: { status: 'ok', workers: 2 },
      telegram_poller: { status: 'ok', active_bots: 1, bots_with_errors: 0 },
      rag: { total_documents: 8, processing: 0, ready: 8, failed: 0 },
    });

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-card-celery')).toBeInTheDocument();
    });

    const celeryCard = screen.getByTestId('dashboard-card-celery');
    expect(celeryCard).toHaveTextContent('Активний');
    expect(celeryCard).toHaveTextContent('Воркерів: 2');

    const pollerCard = screen.getByTestId('dashboard-card-poller');
    expect(pollerCard).toHaveTextContent('Активний');
    expect(pollerCard).toHaveTextContent('Активних ботів: 1 · Помилок: 0');

    const ragCard = screen.getByTestId('dashboard-card-rag');
    expect(ragCard).toHaveTextContent('OK');
    expect(ragCard).toHaveTextContent('Готово: 8 / 8 · В обробці: 0');
  });

  it('renders degraded warnings for failed RAG docs, offline poller, and eager Celery', async () => {
    vi.spyOn(api, 'getSystemHealthDetails').mockResolvedValue({
      status: 'degraded',
      celery: { status: 'eager', workers: 0 },
      telegram_poller: { status: 'offline', active_bots: 2, bots_with_errors: 1 },
      rag: { total_documents: 5, processing: 1, ready: 2, failed: 2 },
    });

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-card-rag')).toBeInTheDocument();
    });

    expect(screen.getByTestId('dashboard-card-celery')).toHaveTextContent('Синхронний');
    expect(screen.getByTestId('dashboard-card-poller')).toHaveTextContent('Офлайн');
    expect(screen.getByTestId('dashboard-card-poller')).toHaveTextContent('Помилок: 1');
    expect(screen.getByTestId('dashboard-card-rag')).toHaveTextContent('Помилки: 2');
    expect(screen.getByTestId('dashboard-card-rag')).toHaveTextContent('Готово: 2 / 5 · В обробці: 1');
  });
});

// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import WorkspaceChatsPage from './WorkspaceChatsPage';

const SAMPLE_WORKSPACES = [
  { id: 1, name: 'Фінансова грамотність' },
  { id: 2, name: 'Курс лідерства' },
];

const SAMPLE_LOGS = [
  {
    id: 101,
    sent_by: 'olena',
    channel: 'web',
    workspace: 'Фінансова грамотність',
    prompt: 'Що таке бюджет?',
    response: 'Бюджет — це план доходів і витрат.',
    feedback: 'up',
    needs_handoff: false,
    sent_at: '2026-11-20T10:00:00Z',
  },
  {
    id: 102,
    sent_by: 'tg:@ivan',
    channel: 'telegram',
    workspace: 'Курс лідерства',
    prompt: 'Як отримати сертифікат?',
    response: 'Завершіть усі модулі курсу.',
    feedback: '',
    needs_handoff: true,
    sent_at: '2026-11-20T10:05:00Z',
  },
  {
    id: 103,
    sent_by: 'widget:edx-1',
    channel: 'widget',
    workspace: 'Фінансова грамотність',
    prompt: 'Коли дедлайн?',
    response: 'До кінця місяця.',
    feedback: 'down',
    needs_handoff: false,
    sent_at: '2026-11-20T10:10:00Z',
  },
];

describe('WorkspaceChatsPage RTL integration', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, 'getWorkspaces').mockResolvedValue(SAMPLE_WORKSPACES);
    vi.spyOn(api, 'getWorkspaceChatLogs').mockResolvedValue({
      count: SAMPLE_LOGS.length,
      results: SAMPLE_LOGS,
    });
    vi.spyOn(api, 'getWorkspaceChatLogsExportUrl').mockImplementation(
      (format) => `/api/chats/logs/export/?export_format=${format}`,
    );
    vi.spyOn(api, 'exportWorkspaceChatLogs').mockResolvedValue();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('renders rows and channel badges for web, telegram, and widget in DOM', async () => {
    const { container } = render(<WorkspaceChatsPage />);

    await waitFor(() => {
      expect(screen.getByText('Що таке бюджет?')).toBeInTheDocument();
    });

    expect(screen.getByText('olena')).toBeInTheDocument();
    expect(screen.getByText('tg:@ivan')).toBeInTheDocument();
    expect(screen.getByText('widget:edx-1')).toBeInTheDocument();

    expect(container.querySelector('.badge--web')).toHaveTextContent('Web');
    expect(container.querySelector('.badge--telegram')).toHaveTextContent('Telegram');
    expect(container.querySelector('.badge--widget')).toHaveTextContent('Widget');
    expect(screen.getByText('Показано 3 з 3')).toBeInTheDocument();
  });

  it('re-fetches logs with channel="telegram" when #filter_channel changes', async () => {
    render(<WorkspaceChatsPage />);

    await waitFor(() => {
      expect(api.getWorkspaceChatLogs).toHaveBeenCalledTimes(1);
    });

    const channelSelect = screen.getByLabelText('Джерело');
    expect(channelSelect.id).toBe('filter_channel');

    fireEvent.change(channelSelect, { target: { value: 'telegram' } });

    await waitFor(() => {
      expect(api.getWorkspaceChatLogs).toHaveBeenLastCalledWith(
        expect.objectContaining({
          channel: 'telegram',
          offset: 0,
        }),
      );
    });
  });

  it('opens export menu with formats and invokes exportWorkspaceChatLogs on click', async () => {
    render(<WorkspaceChatsPage />);

    await waitFor(() => {
      expect(screen.getByText('Що таке бюджет?')).toBeInTheDocument();
    });

    const exportButton = screen.getByRole('button', { name: /Експорт/ });
    expect(exportButton).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(exportButton);

    expect(exportButton).toHaveAttribute('aria-expanded', 'true');
    const menuItems = screen.getAllByRole('menuitem');
    expect(menuItems.map((el) => el.textContent)).toEqual([
      'CSV',
      'JSON',
      'JSONL',
      'JSON (Alpaca)',
    ]);

    fireEvent.click(screen.getByRole('menuitem', { name: 'CSV' }));

    await waitFor(() => {
      expect(api.exportWorkspaceChatLogs).toHaveBeenCalledWith(
        'csv',
        expect.any(Object),
      );
    });
  });
});

import React from 'react';
import { renderToString } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import WorkspacesPage from './WorkspacesPage';
import * as useWorkspacesAdminModule from './workspaces/useWorkspacesAdmin';

describe('WorkspacesPage component', () => {
  it('renders workspaces table with Telegram-боти column header and linked bots', () => {
    vi.spyOn(useWorkspacesAdminModule, 'default').mockReturnValue({
      workspaces: [
        {
          id: 1,
          name: 'Support Team',
          temperature: 0.7,
          users: [{ id: 1, username: 'operator' }],
          model_names: ['llama3:latest'],
          telegram_bots: [
            { id: 10, name: 'Support Bot', bot_username: 'support_bot' },
          ],
          updated_at: '2026-11-13T12:00:00Z',
        },
        {
          id: 2,
          name: 'Marketing Team',
          temperature: 0.5,
          users: [],
          model_names: [],
          telegram_bots: [],
          updated_at: '2026-11-13T13:00:00Z',
        },
      ],
      loading: false,
      error: '',
      formMode: null,
      resetForm: vi.fn(),
      openCreateForm: vi.fn(),
      openEditForm: vi.fn(),
      handleDelete: vi.fn(),
      form: useWorkspacesAdminModule.emptyForm,
      telegramBots: [],
      toggleTelegramBotId: vi.fn(),
    });

    const html = renderToString(<WorkspacesPage />);

    // Header & Column
    expect(html).toContain('Workspaces');
    expect(html).toContain('Телеграм-боти');

    // Workspace 1 with linked bot
    expect(html).toContain('Support Team');
    expect(html).toContain('Support Bot');
    expect(html).toContain('@support_bot');

    // Workspace 2 with empty bots
    expect(html).toContain('Marketing Team');
    expect(html).toContain('—');
  });
});

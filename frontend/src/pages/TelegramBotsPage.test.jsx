import React from 'react';
import { renderToString } from 'react-dom/server';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import TelegramBotsPage, { useTelegramBots, emptyForm } from './TelegramBotsPage';
import * as telegramBotsApi from '../api/telegramBots';
import { api } from '../api/client';

describe('TelegramBotsPage renderToString', () => {
  const sampleBots = [
    {
      id: 1,
      name: 'Бот підтримки',
      bot_username: 'zrozumilo_support_bot',
      token_masked: '123456:***abcd',
      workspace: 10,
      workspace_name: 'Курс лідерства',
      is_active: true,
      last_poll_at: '2026-11-13T12:00:00Z',
      last_error: '',
    },
    {
      id: 2,
      name: 'Бот фінансів',
      bot_username: '',
      token_masked: '987654:***wxyz',
      workspace: null,
      workspace_name: null,
      is_active: false,
      last_poll_at: null,
      last_error: 'Невалідний токен бота',
    },
  ];

  const sampleWorkspaces = [
    { id: 10, name: 'Курс лідерства' },
    { id: 20, name: 'Фінансова грамотність' },
  ];

  it('renders table headers and bot data properly', () => {
    const html = renderToString(
      <TelegramBotsPage
        initialBots={sampleBots}
        initialWorkspaces={sampleWorkspaces}
      />,
    );

    expect(html).toContain('Телеграм-боти');
    expect(html).toContain('Додати бота');

    // Headers
    expect(html).toContain('Назва');
    expect(html).toContain('Username');
    expect(html).toContain('Токен');
    expect(html).toContain('Workspace');
    expect(html).toContain('Статус');
    expect(html).toContain('Дії');

    // Bot 1
    expect(html).toContain('Бот підтримки');
    expect(html).toContain('@zrozumilo_support_bot');
    expect(html).toContain('123456:***abcd');
    expect(html).toContain('Курс лідерства');
    expect(html).toContain('Активний');

    // Bot 2
    expect(html).toContain('Бот фінансів');
    expect(html).toContain('—'); // Empty username
    expect(html).toContain('987654:***wxyz');
    expect(html).toContain('Не привʼязано');
    expect(html).toContain('Вимкнений');
    expect(html).toContain('Ще не опитувався');
    expect(html).toContain('Невалідний токен бота');

    // Action buttons
    expect(html).toContain('Перевірити');
    expect(html).toContain('Редагувати');
    expect(html).toContain('Видалити');
  });

  it('renders empty state when no bots exist', () => {
    const html = renderToString(
      <TelegramBotsPage initialBots={[]} initialWorkspaces={sampleWorkspaces} />,
    );

    expect(html).toContain('Телеграм-ботів ще немає. Додайте першого бота.');
  });

  it('renders create modal with fields and buttons when formMode is create', () => {
    const html = renderToString(
      <TelegramBotsPage
        initialBots={sampleBots}
        initialWorkspaces={sampleWorkspaces}
        initialFormMode="create"
      />,
    );

    expect(html).toContain('Додати телеграм-бота');
    expect(html).toContain('id="bot_name"');
    expect(html).toContain('id="bot_token"');
    expect(html).toContain('id="bot_workspace"');
    expect(html).toContain('id="bot_is_active"');
    expect(html).toContain('Курс лідерства');
    expect(html).toContain('Фінансова грамотність');
    expect(html).toContain('Скасувати');
    expect(html).toContain('Створити');
  });

  it('renders edit modal with populated data when formMode is edit', () => {
    const html = renderToString(
      <TelegramBotsPage
        initialBots={sampleBots}
        initialWorkspaces={sampleWorkspaces}
        initialFormMode="edit"
        initialEditingBotId={1}
        initialForm={{
          name: 'Бот підтримки',
          token: '',
          workspace: '10',
          is_active: true,
        }}
      />,
    );

    expect(html).toContain('Редагувати бота');
    expect(html).toContain('value="Бот підтримки"');
    expect(html).toContain('Залиште поле порожнім, щоб зберегти поточний токен.');
    expect(html).toContain('Зберегти');
  });
});

describe('useTelegramBots hook logic', () => {
  const originalWindow = globalThis.window;

  beforeEach(() => {
    vi.restoreAllMocks();
    globalThis.window = {
      confirm: vi.fn(),
      location: { origin: 'http://localhost' },
    };
  });

  afterEach(() => {
    globalThis.window = originalWindow;
    vi.restoreAllMocks();
  });

  it('provides default emptyForm values and initial state', () => {
    expect(emptyForm.name).toBe('');
    expect(emptyForm.token).toBe('');
    expect(emptyForm.workspace).toBe('');
    expect(emptyForm.is_active).toBe(true);

    let hookValue;
    function TestComponent() {
      hookValue = useTelegramBots({ initialBots: [], initialWorkspaces: [] });
      return React.createElement('div');
    }
    renderToString(React.createElement(TestComponent));

    expect(hookValue.bots).toEqual([]);
    expect(hookValue.workspaces).toEqual([]);
    expect(hookValue.loading).toBe(false);
    expect(hookValue.formMode).toBeNull();
    expect(hookValue.editingBotId).toBeNull();
  });

  it('loads bots and workspaces on loadData', async () => {
    const mockBots = [
      { id: 1, name: 'Bot 1', token_masked: '111:***', is_active: true },
    ];
    const mockWorkspaces = [{ id: 5, name: 'WS 5' }];

    vi.spyOn(telegramBotsApi, 'getTelegramBots').mockResolvedValue(mockBots);
    vi.spyOn(api, 'getWorkspaces').mockResolvedValue(mockWorkspaces);

    let hookValue;
    function TestComponent() {
      hookValue = useTelegramBots({ initialBots: [] });
      return React.createElement('div');
    }
    renderToString(React.createElement(TestComponent));

    const result = await hookValue.loadData();

    expect(telegramBotsApi.getTelegramBots).toHaveBeenCalledTimes(1);
    expect(api.getWorkspaces).toHaveBeenCalledTimes(1);
    expect(result.bots).toEqual(mockBots);
    expect(result.workspaces).toEqual(mockWorkspaces);
  });

  it('handles adding a bot (create mode)', async () => {
    const createdBot = {
      id: 3,
      name: 'Новий бот',
      bot_username: 'new_bot',
      token_masked: '555:***999',
      workspace: 1,
      workspace_name: 'Main WS',
      is_active: true,
      last_poll_at: null,
      last_error: '',
    };
    vi.spyOn(telegramBotsApi, 'createTelegramBot').mockResolvedValue(createdBot);

    let hookValue;
    function TestComponent() {
      hookValue = useTelegramBots({
        initialBots: [],
        initialFormMode: 'create',
        initialForm: {
          name: 'Новий бот',
          token: '555:abcdef999',
          workspace: '1',
          is_active: true,
        },
      });
      return React.createElement('div');
    }
    renderToString(React.createElement(TestComponent));

    const result = await hookValue.handleSubmit();

    expect(telegramBotsApi.createTelegramBot).toHaveBeenCalledWith({
      name: 'Новий бот',
      token: '555:abcdef999',
      workspace: 1,
      is_active: true,
    });
    expect(result).toEqual(createdBot);
  });

  it('validates required fields when creating bot', async () => {
    vi.spyOn(telegramBotsApi, 'createTelegramBot');

    let hookValue;
    function TestComponent() {
      hookValue = useTelegramBots({
        initialBots: [],
        initialFormMode: 'create',
        initialForm: { name: '', token: '', workspace: '', is_active: true },
      });
      return React.createElement('div');
    }
    renderToString(React.createElement(TestComponent));

    // Name empty
    const res1 = await hookValue.handleSubmit();
    expect(res1.error).toBe('Введіть назву бота');
    expect(telegramBotsApi.createTelegramBot).not.toHaveBeenCalled();

    // Name filled but token empty
    const res2 = await hookValue.handleSubmit(null, {
      mode: 'create',
      form: { name: 'Бот', token: '', workspace: '', is_active: true },
    });
    expect(res2.error).toBe('Введіть токен бота');
    expect(telegramBotsApi.createTelegramBot).not.toHaveBeenCalled();
  });

  it('handles editing a bot without changing token', async () => {
    const updatedBot = {
      id: 7,
      name: 'Оновлений бот',
      bot_username: 'old_bot',
      token_masked: '777:***',
      workspace: null,
      workspace_name: null,
      is_active: false,
      last_poll_at: null,
      last_error: '',
    };

    vi.spyOn(telegramBotsApi, 'updateTelegramBot').mockResolvedValue(updatedBot);

    let hookValue;
    function TestComponent() {
      hookValue = useTelegramBots({
        initialBots: [{ id: 7, name: 'Старий бот' }],
        initialFormMode: 'edit',
        initialEditingBotId: 7,
        initialForm: {
          name: 'Оновлений бот',
          token: '',
          workspace: '',
          is_active: false,
        },
      });
      return React.createElement('div');
    }
    renderToString(React.createElement(TestComponent));

    const result = await hookValue.handleSubmit();

    expect(telegramBotsApi.updateTelegramBot).toHaveBeenCalledWith(7, {
      name: 'Оновлений бот',
      workspace: null,
      is_active: false,
    });
    expect(result).toEqual(updatedBot);
  });

  it('includes token in updateTelegramBot payload when token is entered', async () => {
    const updatedBot = {
      id: 8,
      name: 'Бот 8',
      workspace: null,
      is_active: true,
      token_masked: 'new:***',
    };
    vi.spyOn(telegramBotsApi, 'updateTelegramBot').mockResolvedValue(updatedBot);

    let hookValue;
    function TestComponent() {
      hookValue = useTelegramBots({
        initialBots: [{ id: 8, name: 'Бот 8' }],
        initialFormMode: 'edit',
        initialEditingBotId: 8,
        initialForm: {
          name: 'Бот 8',
          token: 'new_raw_token_here',
          workspace: '',
          is_active: true,
        },
      });
      return React.createElement('div');
    }
    renderToString(React.createElement(TestComponent));

    await hookValue.handleSubmit();

    expect(telegramBotsApi.updateTelegramBot).toHaveBeenCalledWith(8, {
      name: 'Бот 8',
      token: 'new_raw_token_here',
      workspace: null,
      is_active: true,
    });
  });

  it('handles clicking verify button calls verifyTelegramBot and returns verified bot', async () => {
    const initialBot = {
      id: 9,
      name: 'Бот перевірки',
      bot_username: '',
      is_active: true,
      last_error: 'Не перевірено',
    };
    const verifiedBot = {
      id: 9,
      name: 'Бот перевірки',
      bot_username: 'checked_bot',
      is_active: true,
      last_error: '',
    };
    vi.spyOn(telegramBotsApi, 'verifyTelegramBot').mockResolvedValue(verifiedBot);

    let hookValue;
    function TestComponent() {
      hookValue = useTelegramBots({ initialBots: [initialBot] });
      return React.createElement('div');
    }
    renderToString(React.createElement(TestComponent));

    const result = await hookValue.handleVerify(9);

    expect(telegramBotsApi.verifyTelegramBot).toHaveBeenCalledWith(9);
    expect(result).toEqual(verifiedBot);
  });

  it('handles deleting a bot when confirmed', async () => {
    const bot = { id: 11, name: 'Бот на видалення' };
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    vi.spyOn(telegramBotsApi, 'deleteTelegramBot').mockResolvedValue(true);

    let hookValue;
    function TestComponent() {
      hookValue = useTelegramBots({ initialBots: [bot] });
      return React.createElement('div');
    }
    renderToString(React.createElement(TestComponent));

    const deleted = await hookValue.handleDelete(11, 'Бот на видалення');

    expect(window.confirm).toHaveBeenCalledWith('Видалити телеграм-бота "Бот на видалення"?');
    expect(telegramBotsApi.deleteTelegramBot).toHaveBeenCalledWith(11);
    expect(deleted).toBe(true);
  });

  it('cancels deletion when user declines confirmation', async () => {
    const bot = { id: 12, name: 'Важливий бот' };
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    vi.spyOn(telegramBotsApi, 'deleteTelegramBot');

    let hookValue;
    function TestComponent() {
      hookValue = useTelegramBots({ initialBots: [bot] });
      return React.createElement('div');
    }
    renderToString(React.createElement(TestComponent));

    const deleted = await hookValue.handleDelete(12, 'Важливий бот');

    expect(telegramBotsApi.deleteTelegramBot).not.toHaveBeenCalled();
    expect(deleted).toBe(false);
  });
});

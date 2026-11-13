import React from 'react';
import { renderToString } from 'react-dom/server';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import {
  useWorkspacesAdmin,
  emptyForm,
  parseIndexes,
  formatIndexes,
} from './useWorkspacesAdmin';
import WorkspaceModal from './WorkspaceModal';
import { api } from '../../api/client';

describe('useWorkspacesAdmin helpers', () => {
  it('parses comma-separated indexes correctly', () => {
    expect(parseIndexes('course_info, courseware_content')).toEqual([
      'course_info',
      'courseware_content',
    ]);
    expect(parseIndexes('  alpha , , beta  , gamma ')).toEqual([
      'alpha',
      'beta',
      'gamma',
    ]);
    expect(parseIndexes('')).toEqual([]);
    expect(parseIndexes(null)).toEqual([]);
  });

  it('formats array of indexes into comma-separated string', () => {
    expect(formatIndexes(['idx1', 'idx2'])).toBe('idx1, idx2');
    expect(formatIndexes([])).toBe('');
    expect(formatIndexes(null)).toBe('');
    expect(formatIndexes(undefined)).toBe('');
  });

  it('provides default emptyForm structure', () => {
    expect(emptyForm.name).toBe('');
    expect(emptyForm.system_prompt).toBe('');
    expect(emptyForm.temperature).toBe(0.7);
    expect(emptyForm.user_ids).toEqual([]);
    expect(emptyForm.telegram_bot_ids).toEqual([]);
    expect(emptyForm.model_name).toBe('');
    expect(emptyForm.search_source).toBe('internal');
  });
});

describe('useWorkspacesAdmin hook', () => {
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
  });

  it('initializes with expected default state and exposed functions', () => {
    let hookValue;
    function TestComponent() {
      hookValue = useWorkspacesAdmin();
      return React.createElement('div');
    }

    renderToString(React.createElement(TestComponent));

    expect(hookValue).toBeDefined();
    expect(hookValue.workspaces).toEqual([]);
    expect(hookValue.users).toEqual([]);
    expect(hookValue.models).toEqual([]);
    expect(hookValue.telegramBots).toEqual([]);
    expect(hookValue.providerModels).toEqual([]);
    expect(hookValue.loading).toBe(true);
    expect(hookValue.formMode).toBeNull();
    expect(hookValue.editingId).toBeNull();
    expect(hookValue.error).toBe('');
    expect(hookValue.form).toEqual(emptyForm);

    expect(typeof hookValue.loadData).toBe('function');
    expect(typeof hookValue.handleSave).toBe('function');
    expect(typeof hookValue.handleDelete).toBe('function');
    expect(typeof hookValue.openCreate).toBe('function');
    expect(typeof hookValue.openEdit).toBe('function');
    expect(typeof hookValue.closeForm).toBe('function');
    expect(typeof hookValue.toggleTelegramBotId).toBe('function');
  });

  it('calls API endpoints when loadData is invoked', async () => {
    vi.spyOn(api, 'getWorkspaces').mockResolvedValue([{ id: 1, name: 'Workspace 1' }]);
    vi.spyOn(api, 'getUsers').mockResolvedValue([{ id: 10, username: 'admin' }]);
    vi.spyOn(api, 'getModels').mockResolvedValue({
      models: [{ name: 'llama3:latest', provider: 'ollama' }],
    });
    vi.spyOn(api, 'getTelegramBots').mockResolvedValue([
      { id: 101, name: 'Support Bot', bot_username: 'support_bot' },
    ]);

    let hookValue;
    function TestComponent() {
      hookValue = useWorkspacesAdmin();
      return React.createElement('div');
    }

    renderToString(React.createElement(TestComponent));

    await hookValue.loadData();

    expect(api.getWorkspaces).toHaveBeenCalledTimes(1);
    expect(api.getUsers).toHaveBeenCalledTimes(1);
    expect(api.getModels).toHaveBeenCalledTimes(1);
    expect(api.getTelegramBots).toHaveBeenCalledTimes(1);
  });

  it('handles delete when user confirms', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    vi.spyOn(api, 'deleteWorkspace').mockResolvedValue(true);
    vi.spyOn(api, 'getWorkspaces').mockResolvedValue([]);
    vi.spyOn(api, 'getUsers').mockResolvedValue([]);
    vi.spyOn(api, 'getModels').mockResolvedValue({ models: [] });
    vi.spyOn(api, 'getTelegramBots').mockResolvedValue([]);

    let hookValue;
    function TestComponent() {
      hookValue = useWorkspacesAdmin();
      return React.createElement('div');
    }

    renderToString(React.createElement(TestComponent));

    await hookValue.handleDelete(5, 'Test Workspace');

    expect(window.confirm).toHaveBeenCalledWith('Видалити workspace "Test Workspace"?');
    expect(api.deleteWorkspace).toHaveBeenCalledWith(5);
  });

  it('does not delete when user cancels confirmation', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    vi.spyOn(api, 'deleteWorkspace').mockResolvedValue(true);

    let hookValue;
    function TestComponent() {
      hookValue = useWorkspacesAdmin();
      return React.createElement('div');
    }

    renderToString(React.createElement(TestComponent));

    await hookValue.handleDelete(5, 'Test Workspace');

    expect(api.deleteWorkspace).not.toHaveBeenCalled();
  });

  it('populates telegram_bot_ids when openEditForm is called', () => {
    vi.spyOn(api, 'getWidgetTokens').mockResolvedValue([]);
    vi.spyOn(api, 'getWorkspaceDocuments').mockResolvedValue([]);
    vi.spyOn(api, 'getWorkspaceRagStats').mockResolvedValue(null);

    let hookValue;
    function TestComponent() {
      hookValue = useWorkspacesAdmin();
      return React.createElement('div');
    }

    renderToString(React.createElement(TestComponent));

    const sampleWorkspace = {
      id: 7,
      name: 'Sales Workspace',
      telegram_bots: [
        { id: 10, name: 'Bot 1' },
        { id: 20, name: 'Bot 2' },
      ],
    };

    hookValue.openEditForm(sampleWorkspace);

    expect(hookValue.formMode).toBe('edit');
    expect(hookValue.editingId).toBe(7);
    expect(hookValue.form.telegram_bot_ids).toEqual([10, 20]);
  });

  it('toggles telegram bot id in form.telegram_bot_ids via toggleTelegramBotId', () => {
    let hookValue;
    function TestComponent() {
      hookValue = useWorkspacesAdmin();
      return React.createElement('div');
    }

    renderToString(React.createElement(TestComponent));

    expect(hookValue.form.telegram_bot_ids).toEqual([]);

    hookValue.toggleTelegramBotId(10);
    expect(hookValue.form.telegram_bot_ids).toEqual([10]);

    hookValue.toggleTelegramBotId(20);
    expect(hookValue.form.telegram_bot_ids).toEqual([10, 20]);

    hookValue.toggleTelegramBotId(10);
    expect(hookValue.form.telegram_bot_ids).toEqual([20]);
  });

  it('includes telegram_bot_ids in API payload on submit for create and edit', async () => {
    const createSpy = vi.spyOn(api, 'createWorkspace').mockResolvedValue({ id: 1 });
    const updateSpy = vi.spyOn(api, 'updateWorkspace').mockResolvedValue({ id: 2 });
    vi.spyOn(api, 'getWorkspaces').mockResolvedValue([]);
    vi.spyOn(api, 'getUsers').mockResolvedValue([]);
    vi.spyOn(api, 'getModels').mockResolvedValue({ models: [] });
    vi.spyOn(api, 'getTelegramBots').mockResolvedValue([]);

    let hookValue;
    function TestComponent() {
      hookValue = useWorkspacesAdmin();
      return React.createElement('div');
    }

    renderToString(React.createElement(TestComponent));

    // Test create
    hookValue.openCreateForm();
    hookValue.handleNameChange({ target: { value: 'New WS' } });
    hookValue.toggleTelegramBotId(42);
    hookValue.toggleTelegramBotId(43);

    await hookValue.handleSave();

    expect(createSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'New WS',
        telegram_bot_ids: [42, 43],
      }),
    );

    // Test edit
    vi.spyOn(api, 'getWidgetTokens').mockResolvedValue([]);
    vi.spyOn(api, 'getWorkspaceDocuments').mockResolvedValue([]);
    vi.spyOn(api, 'getWorkspaceRagStats').mockResolvedValue(null);

    hookValue.openEditForm({
      id: 99,
      name: 'Existing WS',
      telegram_bots: [{ id: 42, name: 'Bot 42' }],
    });
    hookValue.toggleTelegramBotId(42); // deselect 42
    hookValue.toggleTelegramBotId(999); // select 999

    await hookValue.handleSave();

    expect(updateSpy).toHaveBeenCalledWith(
      99,
      expect.objectContaining({
        name: 'Existing WS',
        telegram_bot_ids: [999],
      }),
    );
  });
});

describe('WorkspaceModal component', () => {
  const defaultProps = {
    formMode: null,
    editingId: null,
    form: emptyForm,
    setForm: () => {},
    users: [{ id: 1, username: 'testuser', is_staff: false }],
    providerModels: [{ name: 'llama3:latest', provider: 'ollama' }],
    telegramBots: [],
    toggleTelegramBotId: () => {},
    handleNameChange: () => {},
    handlePromptChange: () => {},
    handleTemperatureChange: () => {},
    toggleUserId: () => {},
    handleModelChange: () => {},
    handleSave: () => {},
    closeForm: () => {},
    widgetTokenLabel: '',
    setWidgetTokenLabel: () => {},
    widgetTokenCourseId: '',
    setWidgetTokenCourseId: () => {},
    handleCreateWidgetToken: () => {},
    newWidgetToken: '',
    widgetEmbedSnippet: '',
    widgetTokens: [],
    handleDeleteWidgetToken: () => {},
    documents: [],
    ragStats: null,
    uploadingDocument: false,
    handleDocumentUpload: () => {},
    handleRetryDocument: () => {},
    handleDeleteDocument: () => {},
    handleReindexFailed: () => {},
    handleUploadMaterial: () => {},
  };

  it('renders nothing when formMode is null', () => {
    const html = renderToString(<WorkspaceModal {...defaultProps} formMode={null} />);
    expect(html).toBe('');
  });

  it('renders create modal when formMode is create', () => {
    const html = renderToString(
      <WorkspaceModal
        {...defaultProps}
        formMode="create"
        form={{ ...emptyForm, name: 'New Team' }}
      />,
    );

    expect(html).toContain('Новий workspace');
    expect(html).toContain('New Team');
    expect(html).toContain('testuser');
    expect(html).toContain('llama3:latest');
    expect(html).toContain('Створити');
    // Does not render edit sections like widget tokens or documents
    expect(html).not.toContain('Widget token для embed');
  });

  it('renders edit modal with sections when formMode is edit', () => {
    const html = renderToString(
      <WorkspaceModal
        {...defaultProps}
        formMode="edit"
        editingId={42}
        form={{ ...emptyForm, name: 'Support Team' }}
      />,
    );

    expect(html).toContain('Редагування workspace');
    expect(html).toContain('Support Team');
    expect(html).toContain('Зберегти');
    // Renders subcomponents
    expect(html).toContain('Widget token для embed');
    expect(html).toContain('Документи (RAG)');
    expect(html).toContain('Аналітика та прогалини знань');
  });

  it('renders telegram bots empty state hint when no bots exist', () => {
    const html = renderToString(
      <WorkspaceModal
        {...defaultProps}
        formMode="create"
        telegramBots={[]}
      />,
    );

    expect(html).toContain('Телеграм-боти');
    expect(html).toContain(
      'Немає створених Телеграм-ботів. Додайте їх у розділі «Телеграм-бот».',
    );
  });

  it('renders telegram bots checkboxes, usernames, and elsewhere note', () => {
    const sampleBots = [
      {
        id: 1,
        name: 'Support Bot',
        bot_username: 'support_ua_bot',
        workspace: 10,
        workspace_name: 'Other WS',
      },
      {
        id: 2,
        name: 'Sales Bot',
        bot_username: '',
        workspace: 42,
        workspace_name: 'Current WS',
      },
      {
        id: 3,
        name: 'Unassigned Bot',
        bot_username: 'unassigned_bot',
        workspace: null,
        workspace_name: null,
      },
    ];

    const html = renderToString(
      <WorkspaceModal
        {...defaultProps}
        formMode="edit"
        editingId={42}
        telegramBots={sampleBots}
        form={{
          ...emptyForm,
          name: 'Current WS',
          telegram_bot_ids: [2],
        }}
      />,
    );

    expect(html).toContain('Телеграм-боти');
    expect(html).toContain('Support Bot');
    expect(html).toContain('@support_ua_bot');
    expect(html).toContain('(зараз у: Other WS)');
    expect(html).toContain('Sales Bot');
    // bot 2 is in current workspace (42), so elsewhere note is NOT shown
    expect(html).not.toContain('(зараз у: Current WS)');
    expect(html).toContain('Unassigned Bot');
    expect(html).toContain('@unassigned_bot');
  });

  it('catches error and logs when loadWidgetTokens fails', async () => {
    vi.spyOn(api, 'getWidgetTokens').mockRejectedValue(new Error('Tokens API down'));
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    let hookValue;
    function TestComponent() {
      hookValue = useWorkspacesAdmin();
      return React.createElement('div');
    }

    renderToString(React.createElement(TestComponent));
    await expect(hookValue.loadWidgetTokens(1)).resolves.not.toThrow();
    expect(consoleSpy).toHaveBeenCalledWith('Failed to load widget tokens:', expect.any(Error));
  });

  it('catches error and logs when loadDocuments fails', async () => {
    vi.spyOn(api, 'getWorkspaceDocuments').mockRejectedValue(new Error('Storage unavailable'));
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    let hookValue;
    function TestComponent() {
      hookValue = useWorkspacesAdmin();
      return React.createElement('div');
    }

    renderToString(React.createElement(TestComponent));
    await expect(hookValue.loadDocuments(1)).resolves.not.toThrow();
    expect(consoleSpy).toHaveBeenCalledWith('Failed to load workspace documents:', expect.any(Error));
  });
});

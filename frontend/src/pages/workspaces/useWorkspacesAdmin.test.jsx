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
  });

  it('calls API endpoints when loadData is invoked', async () => {
    vi.spyOn(api, 'getWorkspaces').mockResolvedValue([{ id: 1, name: 'Workspace 1' }]);
    vi.spyOn(api, 'getUsers').mockResolvedValue([{ id: 10, username: 'admin' }]);
    vi.spyOn(api, 'getModels').mockResolvedValue({
      models: [{ name: 'llama3:latest', provider: 'ollama' }],
    });

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
  });

  it('handles delete when user confirms', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    vi.spyOn(api, 'deleteWorkspace').mockResolvedValue(true);
    vi.spyOn(api, 'getWorkspaces').mockResolvedValue([]);
    vi.spyOn(api, 'getUsers').mockResolvedValue([]);
    vi.spyOn(api, 'getModels').mockResolvedValue({ models: [] });

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
});

describe('WorkspaceModal component', () => {
  const defaultProps = {
    formMode: null,
    editingId: null,
    form: emptyForm,
    setForm: () => {},
    users: [{ id: 1, username: 'testuser', is_staff: false }],
    providerModels: [{ name: 'llama3:latest', provider: 'ollama' }],
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
});

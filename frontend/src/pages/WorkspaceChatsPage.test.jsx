import React from 'react';
import { renderToString } from 'react-dom/server';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import WorkspaceChatsPage, { useWorkspaceChats } from './WorkspaceChatsPage';
import { api } from '../api/client';

function findSelects(element) {
  const selects = [];
  function traverse(node) {
    if (!node || typeof node !== 'object') return;
    if (node.type === 'select') selects.push(node);
    if (Array.isArray(node.props?.children)) {
      node.props.children.forEach(traverse);
    } else if (node.props?.children) {
      traverse(node.props.children);
    }
  }
  traverse(element);
  return selects;
}

describe('WorkspaceChatsPage filters', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders workspace and date range select dropdowns in the toolbar', () => {
    const html = renderToString(<WorkspaceChatsPage />);

    // Workspace filter
    expect(html).toContain('id="filter_workspace"');
    expect(html).toContain('Всі робочі простори');

    // Date range filter
    expect(html).toContain('id="filter_range"');
    expect(html).toContain('Весь час');
    expect(html).toContain('Сьогодні');
    expect(html).toContain('Останні 7 днів');
    expect(html).toContain('Останні 30 днів');
  });

  it('renders workspace options populated from workspaces state', () => {
    let tree;
    function Wrapper() {
      tree = WorkspaceChatsPage({
        initialWorkspaces: [
          { id: 1, name: 'Фінансова грамотність' },
          { id: 2, name: 'Курс лідерства' },
        ],
      });
      return tree;
    }
    const html = renderToString(<Wrapper />);

    expect(html).toContain('Фінансова грамотність');
    expect(html).toContain('Курс лідерства');
  });

  it('allows interacting with workspace and date range select dropdowns', () => {
    let tree;
    function Wrapper() {
      tree = WorkspaceChatsPage({
        initialWorkspaces: [{ id: 42, name: 'Спеціальний простір' }],
      });
      return tree;
    }
    renderToString(<Wrapper />);

    const selects = findSelects(tree);
    const wsSelect = selects.find((s) => s.props.id === 'filter_workspace');
    const rangeSelect = selects.find((s) => s.props.id === 'filter_range');

    expect(wsSelect).toBeDefined();
    expect(wsSelect.props.value).toBe('');
    expect(typeof wsSelect.props.onChange).toBe('function');

    expect(rangeSelect).toBeDefined();
    expect(rangeSelect.props.value).toBe('all');
    expect(typeof rangeSelect.props.onChange).toBe('function');

    // Trigger select onChange handlers without throwing
    expect(() => {
      wsSelect.props.onChange({ target: { value: '42' } });
      rangeSelect.props.onChange({ target: { value: 'today' } });
    }).not.toThrow();
  });

  it('provides useWorkspaceChats hook that triggers api.getWorkspaceChatLogs with workspace_id and range', async () => {
    const mockLogsResponse = {
      count: 1,
      results: [{ id: 10, prompt: 'Test', response: 'Ok', sent_at: '2026-11-09' }],
    };
    vi.spyOn(api, 'getWorkspaceChatLogs').mockResolvedValue(mockLogsResponse);
    vi.spyOn(api, 'getWorkspaces').mockResolvedValue([
      { id: 1, name: 'Простір 1' },
      { id: 2, name: 'Простір 2' },
    ]);

    let hookResult;
    function HookComponent() {
      hookResult = useWorkspaceChats();
      return React.createElement('div');
    }
    renderToString(React.createElement(HookComponent));

    expect(hookResult.workspaceFilter).toBe('');
    expect(hookResult.rangeFilter).toBe('all');

    // Test loadLogs with workspace and range filters
    await hookResult.loadLogs({
      workspace_id: '2',
      range: '7d',
      handoffFilter: 'yes',
      feedbackFilter: 'up',
    });

    expect(api.getWorkspaceChatLogs).toHaveBeenCalledWith(
      expect.objectContaining({
        workspace_id: '2',
        range: '7d',
        needsHandoff: true,
        feedback: 'up',
      }),
    );
  });

  it('updates export URLs and calls exportWorkspaceChatLogs with active filters', async () => {
    vi.spyOn(api, 'exportWorkspaceChatLogs').mockResolvedValue();
    vi.spyOn(api, 'getWorkspaces').mockResolvedValue([]);

    let hookResult;
    function HookComponent() {
      hookResult = useWorkspaceChats();
      return React.createElement('div');
    }
    renderToString(React.createElement(HookComponent));

    await hookResult.handleExport('csv', {
      workspace_id: '3',
      range: '30d',
      needs_handoff: false,
      feedback: 'down',
    });

    expect(api.exportWorkspaceChatLogs).toHaveBeenCalledWith(
      'csv',
      expect.objectContaining({
        workspace_id: '3',
        range: '30d',
        needs_handoff: false,
        feedback: 'down',
      }),
    );
  });
});

describe('ApiClient chats logs parameters and export URL generator', () => {
  it('generates export URL with format, workspace_id, range, and other filters', () => {
    const url = api.getWorkspaceChatLogsExportUrl('csv', {
      workspace_id: 5,
      range: 'today',
      needs_handoff: true,
      feedback: 'up',
    });

    expect(url).toContain('export_format=csv');
    expect(url).toContain('workspace_id=5');
    expect(url).toContain('range=today');
    expect(url).toContain('needs_handoff=true');
    expect(url).toContain('feedback=up');
  });

  it('passes workspace_id and range query parameters in getWorkspaceChatLogs', async () => {
    const originalRequest = api.request;
    api.request = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ count: 0, results: [] }),
    });

    try {
      await api.getWorkspaceChatLogs({
        workspace_id: 12,
        range: '30d',
        needsHandoff: true,
      });

      expect(api.request).toHaveBeenCalledTimes(1);
      const requestedPath = api.request.mock.calls[0][0];
      expect(requestedPath).toContain('workspace_id=12');
      expect(requestedPath).toContain('range=30d');
      expect(requestedPath).toContain('needs_handoff=true');
    } finally {
      api.request = originalRequest;
    }
  });

  it('catches error and logs when api.getWorkspaceChatLogs fails in useWorkspaceChats', async () => {
    vi.spyOn(api, 'getWorkspaceChatLogs').mockRejectedValue(new Error('Logs backend failed'));
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    let hookResult;
    function TestComponent() {
      hookResult = useWorkspaceChats();
      return React.createElement('div');
    }

    renderToString(React.createElement(TestComponent));
    await expect(hookResult.loadLogs()).resolves.not.toThrow();
    expect(consoleSpy).toHaveBeenCalledWith('Failed to load workspace chat logs:', expect.any(Error));
  });
});

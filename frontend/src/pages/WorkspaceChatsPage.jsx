import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import ChatTableAnalysis from '../components/analytics/ChatTableAnalysis';
import WorkspaceChatsFilters from '../components/chats/WorkspaceChatsFilters';
import WorkspaceChatsTable, {
  CHANNEL_META,
  ChannelBadge,
} from '../components/chats/WorkspaceChatsTable';
import { formatChatError } from '../utils/chatError.js';

export const EXPORT_FORMATS = [
  { id: 'csv', label: 'CSV' },
  { id: 'json', label: 'JSON' },
  { id: 'jsonl', label: 'JSONL' },
  { id: 'alpaca', label: 'JSON (Alpaca)' },
];

export const PAGE_SIZE = 50;

export { CHANNEL_META, ChannelBadge };

export function useWorkspaceChats({ initialWorkspaces = [] } = {}) {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [handoffFilter, setHandoffFilter] = useState('all');
  const [feedbackFilter, setFeedbackFilter] = useState('all');
  const [workspaceFilter, setWorkspaceFilter] = useState('');
  const [rangeFilter, setRangeFilter] = useState('all');
  const [channelFilter, setChannelFilter] = useState('all');
  const [workspaces, setWorkspaces] = useState(initialWorkspaces);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [exportOpen, setExportOpen] = useState(false);
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState('');
  const exportRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getWorkspaces()
      .then((data) => {
        if (!cancelled && Array.isArray(data)) {
          setWorkspaces(data);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.error('Failed to load workspaces:', err);
          setError(err.message || 'Не вдалося завантажити робочі простори');
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const loadLogs = useCallback(
    async (overrides = {}) => {
      setLoading(true);
      setError('');
      try {
        const activeWorkspace =
          overrides.workspace_id !== undefined ? overrides.workspace_id : workspaceFilter;
        const activeRange = overrides.range !== undefined ? overrides.range : rangeFilter;
        const activeHandoff =
          overrides.handoffFilter !== undefined ? overrides.handoffFilter : handoffFilter;
        const activeFeedback =
          overrides.feedbackFilter !== undefined ? overrides.feedbackFilter : feedbackFilter;
        const activeChannel =
          overrides.channelFilter !== undefined ? overrides.channelFilter : channelFilter;
        const activeOffset = overrides.offset !== undefined ? overrides.offset : offset;

        const params = {
          limit: PAGE_SIZE,
          offset: activeOffset,
          workspace_id: activeWorkspace || undefined,
          range: activeRange !== 'all' ? activeRange : undefined,
        };
        if (activeHandoff === 'yes') params.needsHandoff = true;
        if (activeHandoff === 'no') params.needsHandoff = false;
        if (activeFeedback !== 'all') params.feedback = activeFeedback;
        if (activeChannel !== 'all') params.channel = activeChannel;

        const data = await api.getWorkspaceChatLogs(params);
        setLogs(data.results || []);
        setTotal(data.count || 0);
      } catch (err) {
        console.error('Failed to load workspace chat logs:', err);
        setError(err.message || 'Не вдалося завантажити чати');
      } finally {
        setLoading(false);
      }
    },
    [offset, handoffFilter, feedbackFilter, workspaceFilter, rangeFilter, channelFilter],
  );

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (exportRef.current && !exportRef.current.contains(event.target)) {
        setExportOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleDelete = async (logId) => {
    if (!window.confirm('Видалити цей запис чату?')) return;

    setError('');
    try {
      await api.deleteWorkspaceChatLog(logId);
      setLogs((prev) => prev.filter((item) => item.id !== logId));
      setTotal((prev) => Math.max(0, prev - 1));
    } catch (err) {
      console.error('Failed to delete workspace chat log:', err);
      setError(err.message || 'Помилка видалення');
    }
  };

  const handleClear = async () => {
    if (!window.confirm('Очистити всі записи Chats Info?')) return;

    setError('');
    try {
      await api.clearWorkspaceChatLogs();
      setLogs([]);
      setTotal(0);
      setOffset(0);
    } catch (err) {
      console.error('Failed to clear workspace chat logs:', err);
      setError(err.message || 'Помилка очищення');
    }
  };

  const loadAnalysis = useCallback(async () => {
    setAnalysisLoading(true);
    setAnalysisError('');
    try {
      const payload = {};
      if (handoffFilter === 'yes') payload.needs_handoff = true;
      if (handoffFilter === 'no') payload.needs_handoff = false;
      if (feedbackFilter !== 'all') payload.feedback = feedbackFilter;
      if (workspaceFilter) payload.workspace_id = workspaceFilter;
      if (rangeFilter !== 'all') payload.range = rangeFilter;
      if (channelFilter !== 'all') payload.channel = channelFilter;
      setAnalysis(await api.analyzeWorkspaceChatLogs(payload));
    } catch (err) {
      console.error('Failed to analyze chat table:', err);
      setAnalysis(null);
      setAnalysisError(
        err?.code === 'ollama_busy'
          ? formatChatError(err)
          : (err.message || 'Не вдалося проаналізувати таблицю'),
      );
    } finally {
      setAnalysisLoading(false);
    }
  }, [feedbackFilter, handoffFilter, workspaceFilter, rangeFilter, channelFilter]);

  useEffect(() => {
    if (!analysisOpen) {
      return;
    }
    loadAnalysis();
  }, [analysisOpen, loadAnalysis]);

  const exportFilters = {
    workspace_id: workspaceFilter || undefined,
    range: rangeFilter !== 'all' ? rangeFilter : undefined,
    needs_handoff: handoffFilter === 'yes' ? true : handoffFilter === 'no' ? false : undefined,
    feedback: feedbackFilter !== 'all' ? feedbackFilter : undefined,
    channel: channelFilter !== 'all' ? channelFilter : undefined,
  };

  const exportItems = EXPORT_FORMATS.map((item) => ({
    ...item,
    url: typeof api.getWorkspaceChatLogsExportUrl === 'function'
      ? api.getWorkspaceChatLogsExportUrl(item.id, exportFilters)
      : undefined,
  }));

  const handleExport = async (format, overrideFilters) => {
    setExportOpen(false);
    setError('');
    try {
      await api.exportWorkspaceChatLogs(format, overrideFilters || exportFilters);
    } catch (err) {
      console.error('Failed to export workspace chat logs:', err);
      setError(err.message || 'Помилка експорту');
    }
  };

  const onWorkspaceFilterChange = (value) => {
    setOffset(0);
    setWorkspaceFilter(value);
  };

  const onRangeFilterChange = (value) => {
    setOffset(0);
    setRangeFilter(value);
  };

  const onHandoffFilterChange = (value) => {
    setOffset(0);
    setHandoffFilter(value);
  };

  const onFeedbackFilterChange = (value) => {
    setOffset(0);
    setFeedbackFilter(value);
  };

  const onChannelFilterChange = (value) => {
    setOffset(0);
    setChannelFilter(value);
  };

  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

  return {
    logs,
    total,
    offset,
    setOffset,
    handoffFilter,
    setHandoffFilter,
    onHandoffFilterChange,
    feedbackFilter,
    setFeedbackFilter,
    onFeedbackFilterChange,
    channelFilter,
    setChannelFilter,
    onChannelFilterChange,
    workspaceFilter,
    setWorkspaceFilter,
    onWorkspaceFilterChange,
    rangeFilter,
    setRangeFilter,
    onRangeFilterChange,
    workspaces,
    setWorkspaces,
    loading,
    error,
    exportOpen,
    setExportOpen,
    analysisOpen,
    setAnalysisOpen,
    analysis,
    analysisLoading,
    analysisError,
    exportRef,
    exportItems,
    exportFilters,
    loadLogs,
    handleDelete,
    handleClear,
    loadAnalysis,
    handleExport,
    canPrev,
    canNext,
  };
}

function WorkspaceChatsPage({ initialWorkspaces } = {}) {
  const {
    logs,
    total,
    setOffset,
    handoffFilter,
    onHandoffFilterChange,
    feedbackFilter,
    onFeedbackFilterChange,
    channelFilter,
    onChannelFilterChange,
    workspaceFilter,
    onWorkspaceFilterChange,
    rangeFilter,
    onRangeFilterChange,
    workspaces,
    loading,
    error,
    exportOpen,
    setExportOpen,
    analysisOpen,
    setAnalysisOpen,
    analysis,
    analysisLoading,
    analysisError,
    exportRef,
    exportItems,
    handleDelete,
    handleClear,
    loadAnalysis,
    handleExport,
    canPrev,
    canNext,
  } = useWorkspaceChats({ initialWorkspaces });

  return (
    <div className="page">
      <header className="page__header page__header--row">
        <div>
          <h2>Chats Info</h2>
          <p>
            Усі записані чати користувачів, відсортовані за датою створення.
          </p>
        </div>
        <div className="page__actions">
          <button
            type="button"
            className="btn btn--secondary"
            aria-expanded={analysisOpen}
            onClick={() => setAnalysisOpen((open) => !open)}
          >
            Аналітика курсів
          </button>
          <div className="dropdown" ref={exportRef}>
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => setExportOpen((open) => !open)}
              aria-expanded={exportOpen}
              aria-haspopup="menu"
            >
              Експорт ▾
            </button>
            {exportOpen && (
              <div className="dropdown__menu" role="menu">
                {exportItems.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="dropdown__item"
                    role="menuitem"
                    data-export-url={item.url}
                    onClick={() => handleExport(item.id)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button
            type="button"
            className="btn btn--ghost"
            onClick={handleClear}
            disabled={total === 0}
          >
            Очистити чати
          </button>
        </div>
      </header>

      {error && <div className="alert alert--error" role="alert">{error}</div>}

      {analysisOpen && (
        <ChatTableAnalysis
          analysis={analysis}
          loading={analysisLoading}
          error={analysisError}
          onRefresh={loadAnalysis}
        />
      )}

      <section className="section">
        <WorkspaceChatsFilters
          workspaceFilter={workspaceFilter}
          onWorkspaceFilterChange={onWorkspaceFilterChange}
          workspaces={workspaces}
          rangeFilter={rangeFilter}
          onRangeFilterChange={onRangeFilterChange}
          channelFilter={channelFilter}
          onChannelFilterChange={onChannelFilterChange}
          handoffFilter={handoffFilter}
          onHandoffFilterChange={onHandoffFilterChange}
          feedbackFilter={feedbackFilter}
          onFeedbackFilterChange={onFeedbackFilterChange}
          shownCount={logs.length}
          total={total}
        />

        <WorkspaceChatsTable
          logs={logs}
          loading={loading}
          canPrev={canPrev}
          canNext={canNext}
          onDelete={handleDelete}
          onPrevPage={() => setOffset((prev) => Math.max(0, prev - PAGE_SIZE))}
          onNextPage={() => setOffset((prev) => prev + PAGE_SIZE)}
        />
      </section>
    </div>
  );
}

export default WorkspaceChatsPage;

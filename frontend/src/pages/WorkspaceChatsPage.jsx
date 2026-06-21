import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { truncateText } from '../embed/utils.js';

const EXPORT_FORMATS = [
  { id: 'csv', label: 'CSV' },
  { id: 'json', label: 'JSON' },
  { id: 'jsonl', label: 'JSONL' },
  { id: 'alpaca', label: 'JSON (Alpaca)' },
];

const PROMPT_PREVIEW_LENGTH = 80;
const RESPONSE_PREVIEW_LENGTH = 120;

function WorkspaceChatsPage() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [exportOpen, setExportOpen] = useState(false);
  const exportRef = useRef(null);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.getWorkspaceChatLogs();
      setLogs(data);
    } catch (err) {
      setError(err.message || 'Не вдалося завантажити чати');
    } finally {
      setLoading(false);
    }
  }, []);

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
    } catch (err) {
      setError(err.message || 'Помилка видалення');
    }
  };

  const handleClear = async () => {
    if (!window.confirm('Очистити всі записи Chats Info?')) return;

    setError('');
    try {
      await api.clearWorkspaceChatLogs();
      setLogs([]);
    } catch (err) {
      setError(err.message || 'Помилка очищення');
    }
  };

  const handleExport = async (format) => {
    setExportOpen(false);
    setError('');
    try {
      await api.exportWorkspaceChatLogs(format);
    } catch (err) {
      setError(err.message || 'Помилка експорту');
    }
  };

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
                {EXPORT_FORMATS.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="dropdown__item"
                    role="menuitem"
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
            disabled={logs.length === 0}
          >
            Очистити чати
          </button>
        </div>
      </header>

      {error && <div className="alert alert--error" role="alert">{error}</div>}

      <section className="section">
        {loading ? (
          <div className="page-loading"><div className="spinner" /></div>
        ) : logs.length === 0 ? (
          <p className="empty-state">Записів чатів ще немає.</p>
        ) : (
          <div className="table-wrapper">
            <table className="table table--workspace-chats">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Sent By</th>
                  <th>Workspace</th>
                  <th>Prompt</th>
                  <th>Response</th>
                  <th>Sent At</th>
                  <th aria-label="Дії" />
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td>{log.id}</td>
                    <td>{log.sent_by}</td>
                    <td>{log.workspace}</td>
                    <td className="table__cell--truncate" title={log.prompt}>
                      {truncateText(log.prompt, PROMPT_PREVIEW_LENGTH)}
                    </td>
                    <td className="table__cell--truncate" title={log.response}>
                      {truncateText(log.response, RESPONSE_PREVIEW_LENGTH)}
                    </td>
                    <td>{log.sent_at}</td>
                    <td className="table__actions">
                      <button
                        type="button"
                        className="btn btn--ghost btn--sm"
                        onClick={() => handleDelete(log.id)}
                        aria-label={`Видалити запис ${log.id}`}
                      >
                        🗑
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

export default WorkspaceChatsPage;

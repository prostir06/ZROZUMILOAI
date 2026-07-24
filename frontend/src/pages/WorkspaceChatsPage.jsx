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
const PAGE_SIZE = 50;

function WorkspaceChatsPage() {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [handoffFilter, setHandoffFilter] = useState('all');
  const [feedbackFilter, setFeedbackFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [exportOpen, setExportOpen] = useState(false);
  const exportRef = useRef(null);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = {
        limit: PAGE_SIZE,
        offset,
      };
      if (handoffFilter === 'yes') params.needsHandoff = true;
      if (handoffFilter === 'no') params.needsHandoff = false;
      if (feedbackFilter !== 'all') params.feedback = feedbackFilter;

      const data = await api.getWorkspaceChatLogs(params);
      setLogs(data.results || []);
      setTotal(data.count || 0);
    } catch (err) {
      setError(err.message || 'Не вдалося завантажити чати');
    } finally {
      setLoading(false);
    }
  }, [offset, handoffFilter, feedbackFilter]);

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

  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

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
            disabled={total === 0}
          >
            Очистити чати
          </button>
        </div>
      </header>

      {error && <div className="alert alert--error" role="alert">{error}</div>}

      <section className="section">
        <div className="form__row" style={{ marginBottom: '1rem', gap: '1rem' }}>
          <div className="form__group">
            <label htmlFor="filter_handoff">Handoff</label>
            <select
              id="filter_handoff"
              className="select"
              value={handoffFilter}
              onChange={(e) => {
                setOffset(0);
                setHandoffFilter(e.target.value);
              }}
            >
              <option value="all">Усі</option>
              <option value="yes">Потрібен handoff</option>
              <option value="no">Без handoff</option>
            </select>
          </div>
          <div className="form__group">
            <label htmlFor="filter_feedback">Feedback</label>
            <select
              id="filter_feedback"
              className="select"
              value={feedbackFilter}
              onChange={(e) => {
                setOffset(0);
                setFeedbackFilter(e.target.value);
              }}
            >
              <option value="all">Усі</option>
              <option value="up">👍</option>
              <option value="down">👎</option>
              <option value="">Без оцінки</option>
            </select>
          </div>
          <p className="auth-card__subtitle" style={{ alignSelf: 'end' }}>
            Показано {logs.length} з {total}
          </p>
        </div>

        {loading ? (
          <div className="page-loading">
            <div className="spinner" aria-label="Завантаження" />
          </div>
        ) : logs.length === 0 ? (
          <p className="empty-state">Записів чатів ще немає.</p>
        ) : (
          <>
            <div className="table-wrapper">
              <table className="table table--workspace-chats">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Sent By</th>
                    <th>Workspace</th>
                    <th>Prompt</th>
                    <th>Response</th>
                    <th>Feedback</th>
                    <th>Handoff</th>
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
                      <td>{log.feedback || '—'}</td>
                      <td>{log.needs_handoff ? 'так' : '—'}</td>
                      <td>{log.sent_at}</td>
                      <td className="table__actions">
                        <button
                          type="button"
                          className="btn btn--ghost btn--sm"
                          onClick={() => handleDelete(log.id)}
                          aria-label={`Видалити запис ${log.id}`}
                        >
                          Видалити
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="form__actions" style={{ marginTop: '1rem' }}>
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                disabled={!canPrev}
                onClick={() => setOffset((prev) => Math.max(0, prev - PAGE_SIZE))}
              >
                Назад
              </button>
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                disabled={!canNext}
                onClick={() => setOffset((prev) => prev + PAGE_SIZE)}
              >
                Далі
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}

export default WorkspaceChatsPage;

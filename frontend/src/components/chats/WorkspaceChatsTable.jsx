import { truncateText } from '../../utils/text.js';

const PROMPT_PREVIEW_LENGTH = 80;
const RESPONSE_PREVIEW_LENGTH = 120;

export const CHANNEL_META = {
  web: { label: 'Web', className: 'badge badge--web' },
  telegram: { label: 'Telegram', className: 'badge badge--telegram' },
  widget: { label: 'Widget', className: 'badge badge--widget' },
};

export function ChannelBadge({ channel }) {
  const meta = CHANNEL_META[channel || 'web'] || CHANNEL_META.web;
  return <span className={meta.className}>{meta.label}</span>;
}

export default function WorkspaceChatsTable({
  logs,
  loading,
  canPrev,
  canNext,
  onDelete,
  onPrevPage,
  onNextPage,
}) {
  if (loading) {
    return (
      <div className="page-loading">
        <div className="spinner" aria-label="Завантаження" />
      </div>
    );
  }

  if (logs.length === 0) {
    return <p className="empty-state">Записів чатів ще немає.</p>;
  }

  return (
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
                <td>
                  <div className="sent-by-cell">
                    <span>{log.sent_by}</span>
                    <ChannelBadge channel={log.channel} />
                  </div>
                </td>
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
                    onClick={() => onDelete(log.id)}
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
          onClick={onPrevPage}
        >
          Назад
        </button>
        <button
          type="button"
          className="btn btn--ghost btn--sm"
          disabled={!canNext}
          onClick={onNextPage}
        >
          Далі
        </button>
      </div>
    </>
  );
}

import { useState } from 'react';

function formatDate(dateStr) {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    if (Number.isNaN(d.getTime())) return dateStr;
    return d.toLocaleString('uk-UA', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

function renderReasonBadge(reason) {
  if (reason === 'low_confidence') {
    return (
      <span
        className="gap-badge gap-badge--low-confidence"
        title="Низька впевненість пошуку RAG або ескалація"
      >
        Низька впевненість RAG
      </span>
    );
  }
  if (reason === 'negative_feedback') {
    return (
      <span
        className="gap-badge gap-badge--negative-feedback"
        title="Студент поставив негативну оцінку відповіді"
      >
        Негативна оцінка
      </span>
    );
  }
  return <span className="gap-badge">{reason || '—'}</span>;
}

function renderChannelBadge(channel) {
  if (channel === 'telegram') {
    return <span className="badge badge--telegram">Telegram</span>;
  }
  if (channel === 'widget') {
    return <span className="badge badge--widget">Widget</span>;
  }
  return <span className="badge badge--web">Web</span>;
}

function renderStatusBadge(isResolved) {
  if (isResolved) {
    return (
      <span
        className="gap-badge gap-badge--resolved"
        title="Прогалину закрито: матеріали додано або відповідь верифіковано"
      >
        Вирішено
      </span>
    );
  }
  return (
    <span
      className="gap-badge gap-badge--pending"
      title="Потребує додавання матеріалу до бази RAG"
    >
      Потребує матеріалу
    </span>
  );
}

/**
 * Table displaying identified knowledge gaps requiring training material uploads.
 *
 * @param {Object} props
 * @param {Array} [props.gaps=[]] - List of knowledge gap log objects.
 * @param {Function} [props.onUploadClick] - Callback fired when 'Додати матеріал' is clicked.
 * @param {Function} [props.onResolveClick] - Callback fired when 'Вирішено'/'Відкрити' is clicked: (gap, nextResolved) => void.
 * @param {number|string|null} [props.resolvingId] - ID of the gap currently being resolved/reopened.
 * @param {string|null} [props.filter] - Optional controlled status filter ('all' | 'open' | 'resolved').
 * @param {Function|null} [props.onFilterChange] - Optional callback when status filter changes.
 * @param {string|null} [props.channelFilter] - Optional controlled channel filter ('all' | 'web' | 'telegram' | 'widget').
 * @param {Function|null} [props.onChannelFilterChange] - Optional callback when channel filter changes.
 */
export default function KnowledgeGapsTable({
  gaps = [],
  onUploadClick,
  onResolveClick,
  resolvingId = null,
  filter: controlledFilter = null,
  onFilterChange = null,
  channelFilter: controlledChannelFilter = null,
  onChannelFilterChange = null,
}) {
  const [internalFilter, setInternalFilter] = useState('all');
  const [internalChannelFilter, setInternalChannelFilter] = useState('all');
  const activeFilter = controlledFilter ?? internalFilter;
  const setFilter = onFilterChange ?? setInternalFilter;
  const activeChannelFilter = controlledChannelFilter ?? internalChannelFilter;
  const setChannelFilter = onChannelFilterChange ?? setInternalChannelFilter;

  const items = Array.isArray(gaps) ? gaps : [];

  if (items.length === 0) {
    return (
      <div className="knowledge-gaps-empty">
        <p className="empty-state">
          Прогалин не виявлено. Всі запитання мають високу впевненість та позитивні оцінки.
        </p>
      </div>
    );
  }

  const openCount = items.filter((gap) => !gap.is_resolved).length;
  const resolvedCount = items.filter((gap) => Boolean(gap.is_resolved)).length;
  const channelCounts = items.reduce(
    (acc, gap) => {
      const channel = gap.channel || 'web';
      if (channel === 'telegram') acc.telegram += 1;
      else if (channel === 'widget') acc.widget += 1;
      else acc.web += 1;
      return acc;
    },
    { web: 0, telegram: 0, widget: 0 },
  );

  const filterOptions = [
    { id: 'all', label: `Всі (${items.length})` },
    { id: 'open', label: `Відкриті (${openCount})` },
    { id: 'resolved', label: `Вирішені (${resolvedCount})` },
  ];

  const channelOptions = [
    { id: 'all', label: `Усі канали (${items.length})` },
    { id: 'web', label: `Web (${channelCounts.web})` },
    { id: 'telegram', label: `Telegram (${channelCounts.telegram})` },
    { id: 'widget', label: `Widget (${channelCounts.widget})` },
  ];

  const filteredItems = items.filter((gap) => {
    if (activeFilter === 'open' && gap.is_resolved) return false;
    if (activeFilter === 'resolved' && !gap.is_resolved) return false;
    if (activeChannelFilter !== 'all') {
      const gapChannel = gap.channel || 'web';
      if (gapChannel !== activeChannelFilter) return false;
    }
    return true;
  });

  return (
    <div className="knowledge-gaps-container">
      <div className="knowledge-gaps-toolbar">
        <div className="knowledge-gaps-filters" role="group" aria-label="Фільтр прогалин знань">
          {filterOptions.map((opt) => (
            <button
              key={opt.id}
              type="button"
              className={`btn btn--sm gap-filter-btn ${
                activeFilter === opt.id ? 'btn--primary gap-filter-btn--active' : 'btn--ghost'
              }`}
              aria-pressed={activeFilter === opt.id}
              onClick={() => setFilter(opt.id)}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <div className="knowledge-gaps-channel-filters" role="group" aria-label="Фільтр прогалин за каналом">
          {channelOptions.map((opt) => (
            <button
              key={opt.id}
              type="button"
              className={`btn btn--sm gap-filter-btn ${
                activeChannelFilter === opt.id ? 'btn--primary gap-filter-btn--active' : 'btn--ghost'
              }`}
              aria-pressed={activeChannelFilter === opt.id}
              onClick={() => setChannelFilter(opt.id)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="table-wrapper knowledge-gaps-wrapper">
        {filteredItems.length === 0 ? (
          <div className="knowledge-gaps-empty">
            <p className="empty-state">Немає прогалин за обраними фільтрами.</p>
          </div>
        ) : (
          <table className="table knowledge-gaps-table" aria-label="Таблиця виявлених прогалин знань">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Джерело</th>
                <th>Питання</th>
                <th>Причина</th>
                <th>Статус</th>
                <th>Відповідь ШІ (прев&apos;ю)</th>
                <th className="table__actions-header">Дія</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.map((gap) => {
                const isResolving = resolvingId === gap.id;
                return (
                  <tr key={gap.id}>
                    <td className="knowledge-gaps-table__date">{formatDate(gap.created_at)}</td>
                    <td className="knowledge-gaps-table__channel">
                      {renderChannelBadge(gap.channel)}
                      {gap.sent_by && (
                        <span className="knowledge-gaps-table__sender" title={gap.sent_by}>
                          {gap.sent_by}
                        </span>
                      )}
                    </td>
                    <td className="knowledge-gaps-table__prompt">
                      <strong>{gap.prompt}</strong>
                    </td>
                    <td className="knowledge-gaps-table__reason">
                      {renderReasonBadge(gap.reason)}
                    </td>
                    <td className="knowledge-gaps-table__status">
                      {renderStatusBadge(gap.is_resolved)}
                    </td>
                    <td className="knowledge-gaps-table__response" title={gap.response_snippet}>
                      {gap.response_snippet || '—'}
                    </td>
                    <td className="table__actions">
                      <div className="gap-actions-group">
                        <button
                          type="button"
                          className="btn btn--ghost btn--sm gap-upload-btn"
                          onClick={() => onUploadClick?.(gap)}
                          title="Додати новий навчальний матеріал у базу RAG"
                        >
                          <span className="gap-upload-btn__icon" aria-hidden="true">➕ </span>
                          Додати матеріал
                        </button>
                        <button
                          type="button"
                          className={`btn btn--ghost btn--sm gap-resolve-btn ${
                            gap.is_resolved ? 'gap-resolve-btn--reopen' : 'gap-resolve-btn--resolve'
                          }`}
                          onClick={() => onResolveClick?.(gap, !gap.is_resolved)}
                          disabled={isResolving}
                          title={gap.is_resolved ? 'Позначити прогалину як відкриту' : 'Позначити як вирішену'}
                        >
                          {isResolving ? (
                            '...'
                          ) : gap.is_resolved ? (
                            '↩ Відкрити'
                          ) : (
                            '✓ Вирішено'
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

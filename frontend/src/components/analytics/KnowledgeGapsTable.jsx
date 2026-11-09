import React, { useState } from 'react';

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
 * @param {string|null} [props.filter] - Optional controlled filter ('all' | 'open' | 'resolved').
 * @param {Function|null} [props.onFilterChange] - Optional callback when active filter changes.
 */
export default function KnowledgeGapsTable({
  gaps = [],
  onUploadClick,
  onResolveClick,
  resolvingId = null,
  filter: controlledFilter = null,
  onFilterChange = null,
}) {
  const [internalFilter, setInternalFilter] = useState('all');
  const activeFilter = controlledFilter ?? internalFilter;
  const setFilter = onFilterChange ?? setInternalFilter;

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

  const filterOptions = [
    { id: 'all', label: `Всі (${items.length})` },
    { id: 'open', label: `Відкриті (${openCount})` },
    { id: 'resolved', label: `Вирішені (${resolvedCount})` },
  ];

  const filteredItems = items.filter((gap) => {
    if (activeFilter === 'open') return !gap.is_resolved;
    if (activeFilter === 'resolved') return Boolean(gap.is_resolved);
    return true;
  });

  return (
    <div className="knowledge-gaps-container">
      <div className="knowledge-gaps-filters" role="group" aria-label="Фільтр прогалин знань">
        {filterOptions.map((opt) => (
          <button
            key={opt.id}
            type="button"
            className={`btn btn--sm gap-filter-btn ${
              activeFilter === opt.id ? 'btn--primary gap-filter-btn--active' : 'btn--ghost'
            }`}
            onClick={() => setFilter(opt.id)}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <div className="table-wrapper knowledge-gaps-wrapper">
        {filteredItems.length === 0 ? (
          <div className="knowledge-gaps-empty">
            <p className="empty-state">Немає прогалин у цій категорії.</p>
          </div>
        ) : (
          <table className="table knowledge-gaps-table" aria-label="Таблиця виявлених прогалин знань">
            <thead>
              <tr>
                <th>Дата</th>
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

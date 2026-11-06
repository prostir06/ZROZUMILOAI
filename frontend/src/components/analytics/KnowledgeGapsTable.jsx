import React from 'react';

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

/**
 * Table displaying identified knowledge gaps requiring training material uploads.
 *
 * @param {Object} props
 * @param {Array} [props.gaps=[]] - List of knowledge gap log objects.
 * @param {Function} [props.onUploadClick] - Callback fired when 'Додати матеріал' is clicked.
 */
export default function KnowledgeGapsTable({ gaps = [], onUploadClick }) {
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

  return (
    <div className="table-wrapper knowledge-gaps-wrapper">
      <table className="table knowledge-gaps-table" aria-label="Таблиця виявлених прогалин знань">
        <thead>
          <tr>
            <th>Дата</th>
            <th>Питання</th>
            <th>Причина</th>
            <th>Відповідь ШІ (прев&apos;ю)</th>
            <th className="table__actions-header">Дія</th>
          </tr>
        </thead>
        <tbody>
          {items.map((gap) => (
            <tr key={gap.id}>
              <td className="knowledge-gaps-table__date">{formatDate(gap.created_at)}</td>
              <td className="knowledge-gaps-table__prompt">
                <strong>{gap.prompt}</strong>
              </td>
              <td className="knowledge-gaps-table__reason">
                {renderReasonBadge(gap.reason)}
              </td>
              <td className="knowledge-gaps-table__response" title={gap.response_snippet}>
                {gap.response_snippet || '—'}
              </td>
              <td className="table__actions">
                <button
                  type="button"
                  className="btn btn--ghost btn--sm gap-upload-btn"
                  onClick={() => onUploadClick?.(gap)}
                  title="Додати новий навчальний матеріал у базу RAG"
                >
                  <span className="gap-upload-btn__icon" aria-hidden="true">➕ </span>
                  Додати матеріал
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

import React from 'react';

/**
 * Metric cards grid presenting high-level workspace analytics KPIs.
 *
 * @param {Object} props
 * @param {Object|null} [props.analytics=null] - Aggregated analytics payload from backend.
 * @param {boolean} [props.isLoading=false] - Optional loading indicator flag.
 */
export default function KpiCards({ analytics = null, isLoading = false }) {
  const data = analytics || {};

  const totalQueries = Number(data.total_queries ?? 0);
  const uniqueUsers = Number(data.unique_users ?? 0);
  const csatScore = Number(data.csat_score ?? 0);
  const feedbackUp = Number(data.feedback_up ?? 0);
  const feedbackDown = Number(data.feedback_down ?? 0);
  const handoffRate = Number(data.handoff_rate ?? 0);
  const handoffCount = Number(data.handoff_count ?? 0);
  const knowledgeGapsCount = Array.isArray(data.knowledge_gaps)
    ? data.knowledge_gaps.length
    : Number(data.knowledge_gaps_count ?? 0);

  const formattedTotalQueries = Number.isFinite(totalQueries) ? totalQueries : 0;
  const formattedCsat = Number.isFinite(csatScore) ? `${csatScore}%` : '0%';
  const formattedHandoffRate = Number.isFinite(handoffRate) ? `${handoffRate}%` : '0%';

  return (
    <section
      className={`kpi-grid ${isLoading ? 'kpi-grid--loading' : ''}`}
      aria-label="Ключові показники аналітики"
    >
      {/* 1. Всього запитів */}
      <article className="kpi-card" data-testid="kpi-card-queries">
        <header className="kpi-card__header">
          <span className="kpi-card__title">Всього запитів</span>
          <span className="kpi-card__icon" aria-hidden="true">💬</span>
        </header>
        <div className="kpi-card__value">
          {formattedTotalQueries}
        </div>
        <footer className="kpi-card__footer">
          <span className="kpi-card__badge">
            <span className="kpi-card__badge-count">{uniqueUsers}</span> унікальних користувачів
          </span>
        </footer>
      </article>

      {/* 2. Індекс корисності */}
      <article className="kpi-card" data-testid="kpi-card-csat">
        <header className="kpi-card__header">
          <span className="kpi-card__title">Індекс корисності</span>
          <span className="kpi-card__icon" aria-hidden="true">⭐</span>
        </header>
        <div className="kpi-card__value">
          {formattedCsat}
        </div>
        <footer className="kpi-card__footer">
          <div className="kpi-card__breakdown">
            <span className="kpi-card__badge kpi-card__badge--success" title="Позитивні відгуки">
              👍 {feedbackUp}
            </span>
            <span className="kpi-card__badge kpi-card__badge--danger" title="Негативні відгуки">
              👎 {feedbackDown}
            </span>
          </div>
        </footer>
      </article>

      {/* 3. Рівень ескалації */}
      <article className="kpi-card" data-testid="kpi-card-handoff">
        <header className="kpi-card__header">
          <span className="kpi-card__title">Рівень ескалації</span>
          <span className="kpi-card__icon" aria-hidden="true">🔀</span>
        </header>
        <div className="kpi-card__value">
          {formattedHandoffRate}
        </div>
        <footer className="kpi-card__footer">
          <span className="kpi-card__meta">
            <span className="kpi-card__meta-count">{handoffCount}</span> передано викладачу
          </span>
        </footer>
      </article>

      {/* 4. Прогалини знань */}
      <article className="kpi-card" data-testid="kpi-card-gaps">
        <header className="kpi-card__header">
          <span className="kpi-card__title">Прогалини знань</span>
          <span className="kpi-card__icon" aria-hidden="true">⚠️</span>
        </header>
        <div className="kpi-card__value">
          {knowledgeGapsCount}
        </div>
        <footer className="kpi-card__footer">
          <span className="kpi-card__meta">
            <span className="kpi-card__meta-count">{knowledgeGapsCount}</span> запитів потребують уваги
          </span>
        </footer>
      </article>
    </section>
  );
}

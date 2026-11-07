/**
 * Дашборд аналізу таблиці Chats Info, який зібрала локальна модель.
 */
export default function ChatTableAnalysis({
  analysis = null,
  loading = false,
  error = '',
  onRefresh,
}) {
  const topics = analysis?.topics || [];
  const problems = analysis?.problems || [];
  const recommendations = analysis?.recommendations || [];

  return (
    <section className="chat-analysis" aria-live="polite" aria-busy={loading}>
      <div className="chat-analysis__header">
        <div>
          <h3 className="chat-analysis__title">Аналіз таблиці</h3>
          {analysis?.model ? (
            <p className="chat-analysis__model">{`Локальна модель: ${analysis.model}`}</p>
          ) : null}
        </div>
        <button
          type="button"
          className="btn btn--ghost btn--sm"
          onClick={onRefresh}
          disabled={loading}
        >
          Оновити
        </button>
      </div>

      {loading ? (
        <div className="page-loading">
          <div className="spinner" aria-label="Модель аналізує таблицю" />
        </div>
      ) : null}

      {error ? (
        <div className="alert alert--error" role="alert">{error}</div>
      ) : null}

      {!loading && analysis ? (
        <>
          <div className="kpi-grid">
            <article className="kpi-card">
              <h4 className="kpi-card__title">Записів</h4>
              <p className="kpi-card__value">{analysis.total ?? 0}</p>
            </article>
            <article className="kpi-card">
              <h4 className="kpi-card__title">Handoff</h4>
              <p className="kpi-card__value">{analysis.handoff ?? 0}</p>
            </article>
            <article className="kpi-card">
              <h4 className="kpi-card__title">Корисні</h4>
              <p className="kpi-card__value">{analysis.feedback_up ?? 0}</p>
            </article>
            <article className="kpi-card">
              <h4 className="kpi-card__title">Некорисні</h4>
              <p className="kpi-card__value">{analysis.feedback_down ?? 0}</p>
            </article>
          </div>

          {analysis.summary ? (
            <p className="chat-analysis__summary">{analysis.summary}</p>
          ) : null}

          {topics.length > 0 ? (
            <div>
              <h4 className="chat-analysis__subtitle">Теми</h4>
              <ul className="chat-analysis__list">
                {topics.map((topic) => (
                  <li key={`${topic.title}-${topic.detail}`}>
                    <strong>{topic.title}</strong>
                    {topic.detail ? ` — ${topic.detail}` : ''}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {problems.length > 0 ? (
            <div>
              <h4 className="chat-analysis__subtitle">Проблеми</h4>
              <ul className="chat-analysis__list">
                {problems.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
          ) : null}

          {recommendations.length > 0 ? (
            <div>
              <h4 className="chat-analysis__subtitle">Рекомендації</h4>
              <ul className="chat-analysis__list">
                {recommendations.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

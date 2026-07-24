/**
 * Секція widget tokens у формі редагування workspace.
 */
export default function WidgetTokensSection({
  widgetTokenLabel,
  setWidgetTokenLabel,
  widgetTokenCourseId,
  setWidgetTokenCourseId,
  onCreateToken,
  newWidgetToken,
  widgetEmbedSnippet,
  widgetTokens,
  onDeleteToken,
}) {
  return (
    <div
      className="form workspaces-section workspaces-section--tokens"
      style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--color-border-subtle)' }}
    >
      <h4 className="section__title">Widget token для embed</h4>
      <p className="auth-card__subtitle" style={{ marginBottom: '1rem' }}>
        Створіть token для віджета на сторонньому сайті. Повний token показується один раз.
        Опційний course id фіксує Meilisearch-фільтр (клієнт не зможе перевизначити).
      </p>

      <div className="form__row">
        <div className="form__group">
          <label htmlFor="widget_token_label">Мітка (опційно)</label>
          <input
            id="widget_token_label"
            value={widgetTokenLabel}
            onChange={(e) => setWidgetTokenLabel(e.target.value)}
            placeholder="Напр. Сайт zrozumilo.com"
          />
        </div>
        <div className="form__group">
          <label htmlFor="widget_token_course">Open edX course id (опційно)</label>
          <input
            id="widget_token_course"
            value={widgetTokenCourseId}
            onChange={(e) => setWidgetTokenCourseId(e.target.value)}
            placeholder="course-v1:org+course+run"
          />
        </div>
        <div className="form__group" style={{ alignSelf: 'end' }}>
          <button type="button" className="btn btn--primary" onClick={onCreateToken}>
            Створити token
          </button>
        </div>
      </div>

      {newWidgetToken && (
        <div className="form__group">
          <label htmlFor="widget_embed_snippet">Код для сайту (збережіть token)</label>
          <textarea
            id="widget_embed_snippet"
            readOnly
            rows={3}
            value={widgetEmbedSnippet}
            className="input"
          />
        </div>
      )}

      {widgetTokens.length > 0 ? (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Мітка / prefix</th>
                <th>Course id</th>
                <th>Створено</th>
                <th>Останнє використання</th>
                <th>Дії</th>
              </tr>
            </thead>
            <tbody>
              {widgetTokens.map((token) => (
                <tr key={token.id}>
                  <td>{token.label || `${token.token_prefix}...`}</td>
                  <td>{token.openedx_course_id || '—'}</td>
                  <td>{new Date(token.created_at).toLocaleString('uk-UA')}</td>
                  <td>
                    {token.last_used_at
                      ? new Date(token.last_used_at).toLocaleString('uk-UA')
                      : '—'}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn btn--danger btn--sm"
                      onClick={() => onDeleteToken(token.id)}
                    >
                      Видалити
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="empty-state">Ще немає widget tokens.</p>
      )}
    </div>
  );
}

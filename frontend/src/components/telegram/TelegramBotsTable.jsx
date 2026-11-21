export default function TelegramBotsTable({
  bots,
  loading,
  verifyingId,
  onVerify,
  onEdit,
  onDelete,
}) {
  return (
    <section className="section">
      {loading ? (
        <div className="page-loading">
          <div className="spinner" role="status" aria-label="Завантаження" />
        </div>
      ) : bots.length === 0 ? (
        <p className="empty-state">Телеграм-ботів ще немає. Додайте першого бота.</p>
      ) : (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Назва</th>
                <th>Username</th>
                <th>Токен</th>
                <th>Workspace</th>
                <th>Статус</th>
                <th>Дії</th>
              </tr>
            </thead>
            <tbody>
              {bots.map((bot) => (
                <tr key={bot.id}>
                  <td>
                    <strong>{bot.name}</strong>
                  </td>
                  <td>
                    {bot.bot_username ? `@${bot.bot_username}` : '—'}
                  </td>
                  <td>
                    <code className="api-key api-key--muted">
                      {bot.token_masked || '—'}
                    </code>
                  </td>
                  <td>
                    {bot.workspace_name ? (
                      <span className="badge">{bot.workspace_name}</span>
                    ) : (
                      'Не привʼязано'
                    )}
                  </td>
                  <td>
                    <div className="bot-status-stack">
                      <span
                        className={`status-badge ${
                          bot.is_active ? 'status-badge--ok' : 'status-badge--error'
                        }`}
                      >
                        {bot.is_active ? 'Активний' : 'Вимкнений'}
                      </span>
                      <small className="bot-status-meta">
                        {bot.last_poll_at
                          ? new Date(bot.last_poll_at).toLocaleString('uk-UA')
                          : 'Ще не опитувався'}
                      </small>
                      {bot.last_error && (
                        <span
                          className="status-badge status-badge--error bot-status-error"
                          title={bot.last_error}
                        >
                          {bot.last_error}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="table__actions">
                    <button
                      type="button"
                      className="btn btn--ghost btn--sm"
                      disabled={verifyingId === bot.id}
                      onClick={() => onVerify(bot.id)}
                    >
                      {verifyingId === bot.id ? 'Перевірка...' : 'Перевірити'}
                    </button>
                    <button
                      type="button"
                      className="btn btn--ghost btn--sm"
                      onClick={() => onEdit(bot)}
                    >
                      Редагувати
                    </button>
                    <button
                      type="button"
                      className="btn btn--danger btn--sm"
                      onClick={() => onDelete(bot.id, bot.name)}
                    >
                      Видалити
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

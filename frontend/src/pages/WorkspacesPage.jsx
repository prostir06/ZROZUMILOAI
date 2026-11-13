import useWorkspacesAdmin from './workspaces/useWorkspacesAdmin';
import WorkspaceModal from './workspaces/WorkspaceModal';

function WorkspacesPage() {
  const admin = useWorkspacesAdmin();
  const {
    workspaces,
    loading,
    error,
    formMode,
    resetForm,
    openCreateForm,
    openEditForm,
    handleDelete,
  } = admin;

  return (
    <div className="page">
      <header className="page__header page__header--row">
        <div>
          <h2>Workspaces</h2>
          <p>Групуйте моделі та користувачів для спільної роботи</p>
        </div>
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => (formMode ? resetForm() : openCreateForm())}
        >
          {formMode ? 'Скасувати' : 'Створити workspace'}
        </button>
      </header>

      {error && <div className="alert alert--error" role="alert">{error}</div>}

      <WorkspaceModal {...admin} />

      <section className="section">
        {loading ? (
          <div className="page-loading"><div className="spinner" /></div>
        ) : workspaces.length === 0 ? (
          <p className="empty-state">Ще немає workspace. Створіть перший.</p>
        ) : (
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Назва</th>
                  <th>Температура</th>
                  <th>Користувачі</th>
                  <th>Модель</th>
                  <th>Телеграм-боти</th>
                  <th>Оновлено</th>
                  <th>Дії</th>
                </tr>
              </thead>
              <tbody>
                {workspaces.map((workspace) => (
                  <tr key={workspace.id}>
                    <td><strong>{workspace.name}</strong></td>
                    <td>{workspace.temperature ?? 0.7}</td>
                    <td>
                      {workspace.users?.length > 0
                        ? workspace.users.map((user) => user.username).join(', ')
                        : '—'}
                    </td>
                    <td>{workspace.model_names?.[0] || '—'}</td>
                    <td>
                      {workspace.telegram_bots?.length > 0 ? (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
                          {workspace.telegram_bots.map((bot) => (
                            <span key={bot.id} className="badge">
                              {bot.name}{bot.bot_username ? ` (@${bot.bot_username})` : ''}
                            </span>
                          ))}
                        </div>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td>
                      {new Date(workspace.updated_at).toLocaleString('uk-UA')}
                    </td>
                    <td className="table__actions">
                      <button
                        type="button"
                        className="btn btn--ghost btn--sm"
                        onClick={() => openEditForm(workspace)}
                      >
                        Редагувати
                      </button>
                      <button
                        type="button"
                        className="btn btn--danger btn--sm"
                        onClick={() => handleDelete(workspace.id, workspace.name)}
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
    </div>
  );
}

export default WorkspacesPage;

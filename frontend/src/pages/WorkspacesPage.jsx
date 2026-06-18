import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';

const emptyForm = {
  name: '',
  system_prompt: '',
  temperature: 0.7,
  user_ids: [],
  model_names: [],
};

function WorkspacesPage() {
  const [workspaces, setWorkspaces] = useState([]);
  const [users, setUsers] = useState([]);
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [formMode, setFormMode] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState('');
  const [form, setForm] = useState(emptyForm);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [workspacesData, usersData, modelsData] = await Promise.all([
        api.getWorkspaces(),
        api.getUsers(),
        api.getModels().catch(() => ({ models: [] })),
      ]);
      setWorkspaces(workspacesData);
      setUsers(usersData);
      setModels(modelsData.models || []);
    } catch {
      setError('Не вдалося завантажити дані');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const resetForm = () => {
    setForm(emptyForm);
    setFormMode(null);
    setEditingId(null);
  };

  const openCreateForm = () => {
    setError('');
    setForm(emptyForm);
    setFormMode('create');
    setEditingId(null);
  };

  const openEditForm = (workspace) => {
    setError('');
    setForm({
      name: workspace.name,
      system_prompt: workspace.system_prompt || '',
      temperature: workspace.temperature ?? 0.7,
      user_ids: workspace.users.map((user) => user.id),
      model_names: [...(workspace.model_names || [])],
    });
    setFormMode('edit');
    setEditingId(workspace.id);
  };

  const handleNameChange = (event) => {
    setForm((prev) => ({ ...prev, name: event.target.value }));
  };

  const handlePromptChange = (event) => {
    setForm((prev) => ({ ...prev, system_prompt: event.target.value }));
  };

  const handleTemperatureChange = (event) => {
    setForm((prev) => ({ ...prev, temperature: Number(event.target.value) }));
  };

  const toggleUserId = (userId) => {
    setForm((prev) => ({
      ...prev,
      user_ids: prev.user_ids.includes(userId)
        ? prev.user_ids.filter((id) => id !== userId)
        : [...prev.user_ids, userId],
    }));
  };

  const toggleModelName = (modelName) => {
    setForm((prev) => ({
      ...prev,
      model_names: prev.model_names.includes(modelName)
        ? prev.model_names.filter((name) => name !== modelName)
        : [...prev.model_names, modelName],
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');

    const payload = {
      name: form.name.trim(),
      system_prompt: form.system_prompt.trim(),
      temperature: form.temperature,
      user_ids: form.user_ids,
      model_names: form.model_names,
    };

    try {
      if (formMode === 'edit') {
        await api.updateWorkspace(editingId, payload);
      } else {
        await api.createWorkspace(payload);
      }
      resetForm();
      loadData();
    } catch (err) {
      setError(err.message || 'Помилка збереження workspace');
    }
  };

  const handleDelete = async (workspaceId, name) => {
    if (!window.confirm(`Видалити workspace "${name}"?`)) return;

    setError('');
    try {
      await api.deleteWorkspace(workspaceId);
      if (editingId === workspaceId) {
        resetForm();
      }
      loadData();
    } catch (err) {
      setError(err.message || 'Помилка видалення workspace');
    }
  };

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

      {formMode && (
        <section className="section card">
          <h3 className="section__title">
            {formMode === 'edit' ? 'Редагування workspace' : 'Новий workspace'}
          </h3>
          <form onSubmit={handleSubmit} className="form">
            <div className="form__group">
              <label htmlFor="workspace_name">Назва</label>
              <input
                id="workspace_name"
                value={form.name}
                onChange={handleNameChange}
                required
                placeholder="Напр. Команда підтримки"
              />
            </div>

            <div className="form__group">
              <label htmlFor="workspace_prompt">Системний промпт</label>
              <textarea
                id="workspace_prompt"
                value={form.system_prompt}
                onChange={handlePromptChange}
                rows={4}
                placeholder="Інструкції для моделі в цьому workspace..."
              />
            </div>

            <div className="form__group">
              <label htmlFor="workspace_temperature">
                Температура: {form.temperature.toFixed(1)}
              </label>
              <input
                id="workspace_temperature"
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={form.temperature}
                onChange={handleTemperatureChange}
              />
            </div>

            <div className="form__row">
              <div className="form__group">
                <span className="form__group-label">Користувачі</span>
                <div className="checkbox-list">
                  {users.length === 0 ? (
                    <p className="empty-state">Немає користувачів</p>
                  ) : (
                    users.map((user) => (
                      <label key={user.id} className="checkbox">
                        <input
                          type="checkbox"
                          checked={form.user_ids.includes(user.id)}
                          onChange={() => toggleUserId(user.id)}
                        />
                        {user.username}
                        {user.is_staff && ' (адмін)'}
                      </label>
                    ))
                  )}
                </div>
              </div>

              <div className="form__group">
                <span className="form__group-label">Моделі</span>
                <div className="checkbox-list">
                  {models.length === 0 ? (
                    <p className="empty-state">Немає встановлених моделей</p>
                  ) : (
                    models.map((model) => (
                      <label key={model.name} className="checkbox">
                        <input
                          type="checkbox"
                          checked={form.model_names.includes(model.name)}
                          onChange={() => toggleModelName(model.name)}
                        />
                        {model.name}
                      </label>
                    ))
                  )}
                </div>
              </div>
            </div>

            <div className="form__actions">
              <button type="submit" className="btn btn--primary">
                {formMode === 'edit' ? 'Зберегти' : 'Створити'}
              </button>
              <button type="button" className="btn btn--ghost" onClick={resetForm}>
                Скасувати
              </button>
            </div>
          </form>
        </section>
      )}

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
                  <th>Моделі</th>
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
                      {workspace.users.length > 0
                        ? workspace.users.map((user) => user.username).join(', ')
                        : '—'}
                    </td>
                    <td>
                      {workspace.model_names?.length > 0
                        ? workspace.model_names.join(', ')
                        : '—'}
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

import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';

const emptyForm = {
  name: '',
  system_prompt: '',
  temperature: 0.7,
  user_ids: [],
  model_name: '',
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
  const [widgetTokens, setWidgetTokens] = useState([]);
  const [newWidgetToken, setNewWidgetToken] = useState('');
  const [widgetTokenLabel, setWidgetTokenLabel] = useState('');
  const [documents, setDocuments] = useState([]);
  const [uploadingDocument, setUploadingDocument] = useState(false);

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
    setWidgetTokens([]);
    setNewWidgetToken('');
    setWidgetTokenLabel('');
    setDocuments([]);
  };

  const loadWidgetTokens = async (workspaceId) => {
    try {
      const tokens = await api.getWidgetTokens(workspaceId);
      setWidgetTokens(tokens);
    } catch {
      setWidgetTokens([]);
    }
  };

  const loadDocuments = async (workspaceId) => {
    try {
      const docs = await api.getWorkspaceDocuments(workspaceId);
      setDocuments(docs);
    } catch {
      setDocuments([]);
    }
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
      model_name: workspace.model_names?.[0] || '',
    });
    setFormMode('edit');
    setEditingId(workspace.id);
    loadWidgetTokens(workspace.id);
    loadDocuments(workspace.id);
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

  const handleModelChange = (event) => {
    setForm((prev) => ({ ...prev, model_name: event.target.value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');

    const payload = {
      name: form.name.trim(),
      system_prompt: form.system_prompt.trim(),
      temperature: form.temperature,
      user_ids: form.user_ids,
      model_names: form.model_name ? [form.model_name] : [],
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

  const handleCreateWidgetToken = async () => {
    if (!editingId) return;
    setError('');
    setNewWidgetToken('');
    try {
      const data = await api.createWidgetToken(editingId, widgetTokenLabel.trim());
      setNewWidgetToken(data.token);
      setWidgetTokenLabel('');
      loadWidgetTokens(editingId);
    } catch (err) {
      setError(err.message || 'Помилка створення widget token');
    }
  };

  const handleDeleteWidgetToken = async (tokenId) => {
    if (!editingId || !window.confirm('Видалити widget token? Віджет на сайті перестане працювати.')) {
      return;
    }
    setError('');
    try {
      await api.deleteWidgetToken(editingId, tokenId);
      loadWidgetTokens(editingId);
    } catch (err) {
      setError(err.message || 'Помилка видалення token');
    }
  };

  const handleDocumentUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file || !editingId) return;

    setError('');
    setUploadingDocument(true);
    try {
      await api.uploadWorkspaceDocument(editingId, file);
      await loadDocuments(editingId);
    } catch (err) {
      setError(err.message || 'Помилка завантаження документа');
    } finally {
      setUploadingDocument(false);
      event.target.value = '';
    }
  };

  const handleDeleteDocument = async (documentId, filename) => {
    if (!editingId || !window.confirm(`Видалити документ "${filename}"?`)) {
      return;
    }
    setError('');
    try {
      await api.deleteWorkspaceDocument(editingId, documentId);
      loadDocuments(editingId);
    } catch (err) {
      setError(err.message || 'Помилка видалення документа');
    }
  };

  const documentStatusLabel = (status) => {
    if (status === 'ready') return 'Готовий';
    if (status === 'processing') return 'Обробка';
    if (status === 'failed') return 'Помилка';
    return status;
  };

  const widgetEmbedSnippet = newWidgetToken
    ? `<script src="${window.location.origin}/widget.js" data-widget-token="${newWidgetToken}" data-title="Підтримка"></script>`
    : '';

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
                <label htmlFor="workspace_model">Модель</label>
                {models.length === 0 ? (
                  <p className="empty-state">Немає встановлених моделей</p>
                ) : (
                  <select
                    id="workspace_model"
                    value={form.model_name}
                    onChange={handleModelChange}
                  >
                    <option value="">— Не обрано —</option>
                    {models.map((model) => (
                      <option key={model.name} value={model.name}>
                        {model.name}
                      </option>
                    ))}
                  </select>
                )}
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

          {formMode === 'edit' && (
            <div className="form" style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--color-border-subtle)' }}>
              <h4 className="section__title">Widget token для embed</h4>
              <p className="auth-card__subtitle" style={{ marginBottom: '1rem' }}>
                Створіть token для віджета на сторонньому сайті. Повний token показується один раз.
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
                <div className="form__group" style={{ alignSelf: 'end' }}>
                  <button
                    type="button"
                    className="btn btn--primary"
                    onClick={handleCreateWidgetToken}
                  >
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
                        <th>Створено</th>
                        <th>Останнє використання</th>
                        <th>Дії</th>
                      </tr>
                    </thead>
                    <tbody>
                      {widgetTokens.map((token) => (
                        <tr key={token.id}>
                          <td>{token.label || `${token.token_prefix}...`}</td>
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
                              onClick={() => handleDeleteWidgetToken(token.id)}
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
                <p className="empty-state">Ще немає widget token.</p>
              )}
            </div>
          )}

          {formMode === 'edit' && (
            <div className="form" style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--color-border-subtle)' }}>
              <h4 className="section__title">Документи (RAG)</h4>
              <p className="auth-card__subtitle" style={{ marginBottom: '1rem' }}>
                Завантажте TXT, MD або PDF. При чаті модель отримує релевантні фрагменти з цих документів.
                Потрібна embedding-модель Ollama: <code>nomic-embed-text</code>.
              </p>

              <div className="form__group">
                <label htmlFor="workspace_document_upload">Завантажити файл</label>
                <input
                  id="workspace_document_upload"
                  type="file"
                  accept=".txt,.md,.markdown,.pdf"
                  onChange={handleDocumentUpload}
                  disabled={uploadingDocument}
                />
                {uploadingDocument && (
                  <p className="auth-card__subtitle">Індексація документа…</p>
                )}
              </div>

              {documents.length > 0 ? (
                <div className="table-wrapper">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Файл</th>
                        <th>Статус</th>
                        <th>Фрагментів</th>
                        <th>Завантажено</th>
                        <th>Дії</th>
                      </tr>
                    </thead>
                    <tbody>
                      {documents.map((doc) => (
                        <tr key={doc.id}>
                          <td>
                            <strong>{doc.original_filename}</strong>
                            {doc.status === 'failed' && doc.error_message && (
                              <div className="auth-card__subtitle">{doc.error_message}</div>
                            )}
                          </td>
                          <td>{documentStatusLabel(doc.status)}</td>
                          <td>{doc.chunk_count || '—'}</td>
                          <td>{new Date(doc.created_at).toLocaleString('uk-UA')}</td>
                          <td>
                            <button
                              type="button"
                              className="btn btn--danger btn--sm"
                              onClick={() => handleDeleteDocument(doc.id, doc.original_filename)}
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
                <p className="empty-state">Ще немає документів для RAG.</p>
              )}
            </div>
          )}
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
                  <th>Модель</th>
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
                    <td>{workspace.model_names?.[0] || '—'}</td>
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

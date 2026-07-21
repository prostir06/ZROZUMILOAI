import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';

const emptyForm = {
  name: '',
  system_prompt: '',
  temperature: 0.7,
  user_ids: [],
  model_name: '',
  llm_provider: 'ollama',
  gemini_api_key: '',
  gemini_api_key_set: false,
  search_source: 'internal',
  meilisearch_url: '',
  meilisearch_api_key: '',
  meilisearch_index_prefix: 'tutor_',
  meilisearch_indexes: 'course_info, courseware_content',
  meilisearch_course_id: '',
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
  const [ragStats, setRagStats] = useState(null);

  const providerModels = models.filter(
    (model) => (model.provider || 'ollama') === form.llm_provider,
  );

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
    setRagStats(null);
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
      const [docs, stats] = await Promise.all([
        api.getWorkspaceDocuments(workspaceId),
        api.getWorkspaceRagStats(workspaceId).catch(() => null),
      ]);
      setDocuments(docs);
      setRagStats(stats);
    } catch {
      setDocuments([]);
      setRagStats(null);
    }
  };

  // P1: polling статусу processing після async ingest.
  useEffect(() => {
    if (!editingId) {
      return undefined;
    }
    const hasProcessing = documents.some((doc) => doc.status === 'processing');
    if (!hasProcessing) {
      return undefined;
    }
    const timer = setInterval(() => {
      loadDocuments(editingId);
    }, 2500);
    return () => clearInterval(timer);
  }, [editingId, documents]);

  const openCreateForm = () => {
    setError('');
    setForm(emptyForm);
    setFormMode('create');
    setEditingId(null);
  };

  const parseIndexes = (value) => value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);

  const formatIndexes = (indexes) => (indexes?.length ? indexes.join(', ') : '');

  const openEditForm = (workspace) => {
    setError('');
    setForm({
      name: workspace.name,
      system_prompt: workspace.system_prompt || '',
      temperature: workspace.temperature ?? 0.7,
      user_ids: workspace.users.map((user) => user.id),
      model_name: workspace.model_names?.[0] || '',
      llm_provider: workspace.llm_provider || 'ollama',
      gemini_api_key: '',
      gemini_api_key_set: Boolean(workspace.gemini_api_key_set),
      search_source: workspace.search_source || 'internal',
      meilisearch_url: workspace.meilisearch_url || '',
      meilisearch_api_key: '',
      meilisearch_index_prefix: workspace.meilisearch_index_prefix || 'tutor_',
      meilisearch_indexes: formatIndexes(workspace.meilisearch_indexes) || 'course_info, courseware_content',
      meilisearch_course_id: workspace.meilisearch_course_id || '',
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

  const handleProviderChange = (event) => {
    const llm_provider = event.target.value;
    setForm((prev) => {
      const nextModels = models.filter(
        (model) => (model.provider || 'ollama') === llm_provider,
      );
      const modelStillValid = nextModels.some(
        (model) => model.name === prev.model_name,
      );
      return {
        ...prev,
        llm_provider,
        model_name: modelStillValid ? prev.model_name : '',
      };
    });
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
      llm_provider: form.llm_provider,
      search_source: form.search_source,
      meilisearch_url: form.meilisearch_url.trim(),
      meilisearch_index_prefix: form.meilisearch_index_prefix.trim(),
      meilisearch_indexes: parseIndexes(form.meilisearch_indexes),
      meilisearch_course_id: form.meilisearch_course_id.trim(),
    };

    if (form.meilisearch_api_key.trim()) {
      payload.meilisearch_api_key = form.meilisearch_api_key.trim();
    }
    if (form.gemini_api_key.trim()) {
      payload.gemini_api_key = form.gemini_api_key.trim();
    }

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

  const handleRetryDocument = async (documentId) => {
    if (!editingId) return;
    setError('');
    try {
      await api.retryWorkspaceDocument(editingId, documentId);
      await loadDocuments(editingId);
    } catch (err) {
      setError(err.message || 'Помилка повторної індексації');
    }
  };

  const handleReindexFailed = async () => {
    if (!editingId) return;
    setError('');
    try {
      await api.reindexFailedWorkspaceDocuments(editingId);
      await loadDocuments(editingId);
    } catch (err) {
      setError(err.message || 'Помилка reindex');
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
                <label htmlFor="workspace_llm_provider">LLM провайдер</label>
                <select
                  id="workspace_llm_provider"
                  value={form.llm_provider}
                  onChange={handleProviderChange}
                >
                  <option value="ollama">Ollama (локально)</option>
                  <option value="gemini">Google Gemini (API)</option>
                </select>
              </div>

              {form.llm_provider === 'gemini' && (
                <div className="form__group">
                  <label htmlFor="workspace_gemini_api_key">Gemini API key</label>
                  <input
                    id="workspace_gemini_api_key"
                    type="password"
                    value={form.gemini_api_key}
                    onChange={(e) => setForm((prev) => ({
                      ...prev,
                      gemini_api_key: e.target.value,
                    }))}
                    placeholder={
                      formMode === 'edit' && form.gemini_api_key_set
                        ? 'Залиште порожнім, щоб не змінювати'
                        : 'Ключ з Google AI Studio'
                    }
                    autoComplete="new-password"
                  />
                  <p className="auth-card__subtitle">
                    Отримайте ключ на{' '}
                    <a
                      href="https://aistudio.google.com/apikey"
                      target="_blank"
                      rel="noreferrer"
                    >
                      aistudio.google.com
                    </a>
                    . Альтернатива — глобальний <code>GEMINI_API_KEY</code> у .env.
                  </p>
                </div>
              )}

              <div className="form__group">
                <label htmlFor="workspace_model">Модель</label>
                {providerModels.length === 0 ? (
                  <p className="empty-state">
                    {form.llm_provider === 'gemini'
                      ? 'Немає моделей Gemini у налаштуваннях сервера'
                      : 'Немає встановлених моделей Ollama'}
                  </p>
                ) : (
                  <select
                    id="workspace_model"
                    value={form.model_name}
                    onChange={handleModelChange}
                  >
                    <option value="">— Не обрано —</option>
                    {providerModels.map((model) => (
                      <option key={model.name} value={model.name}>
                        {model.name}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            </div>

            <div className="form" style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--color-border-subtle)' }}>
              <h4 className="section__title">Пошук Open edX (Meilisearch)</h4>
              <p className="auth-card__subtitle" style={{ marginBottom: '1rem' }}>
                Meilisearch Tutor: префікс <code>tutor_</code>, індекси
                <code>tutor_course_info</code> та <code>tutor_courseware_content</code>.
              </p>

              <div className="form__group">
                <label htmlFor="workspace_search_source">Джерело контексту для чату</label>
                <select
                  id="workspace_search_source"
                  value={form.search_source}
                  onChange={(e) => setForm((prev) => ({ ...prev, search_source: e.target.value }))}
                >
                  <option value="internal">Локальні документи (RAG)</option>
                  <option value="meilisearch">Open edX Meilisearch</option>
                  <option value="hybrid">RAG + Meilisearch</option>
                </select>
              </div>

              {form.search_source !== 'internal' && (
                <>
                  <div className="form__group">
                    <label htmlFor="workspace_meilisearch_url">Meilisearch URL</label>
                    <input
                      id="workspace_meilisearch_url"
                      value={form.meilisearch_url}
                      onChange={(e) => setForm((prev) => ({ ...prev, meilisearch_url: e.target.value }))}
                      placeholder="meilisearch.local.openedx.io"
                    />
                  </div>

                  <div className="form__group">
                    <label htmlFor="workspace_meilisearch_api_key">API key</label>
                    <input
                      id="workspace_meilisearch_api_key"
                      type="password"
                      value={form.meilisearch_api_key}
                      onChange={(e) => setForm((prev) => ({ ...prev, meilisearch_api_key: e.target.value }))}
                      placeholder={formMode === 'edit' ? 'Залиште порожнім, щоб не змінювати' : ''}
                      autoComplete="new-password"
                    />
                  </div>

                  <div className="form__row">
                    <div className="form__group">
                      <label htmlFor="workspace_meilisearch_prefix">Префікс індексів</label>
                      <input
                        id="workspace_meilisearch_prefix"
                        value={form.meilisearch_index_prefix}
                        onChange={(e) => setForm((prev) => ({ ...prev, meilisearch_index_prefix: e.target.value }))}
                        placeholder="tutor_"
                      />
                    </div>
                    <div className="form__group">
                      <label htmlFor="workspace_meilisearch_indexes">Індекси (через кому)</label>
                      <input
                        id="workspace_meilisearch_indexes"
                        value={form.meilisearch_indexes}
                        onChange={(e) => setForm((prev) => ({ ...prev, meilisearch_indexes: e.target.value }))}
                        placeholder="course_info, courseware_content"
                      />
                    </div>
                  </div>

                  <div className="form__group">
                    <label htmlFor="workspace_meilisearch_course_id">Course ID (фільтр, опційно)</label>
                    <input
                      id="workspace_meilisearch_course_id"
                      value={form.meilisearch_course_id}
                      onChange={(e) => setForm((prev) => ({ ...prev, meilisearch_course_id: e.target.value }))}
                      placeholder="course-v1:ORG+COURSE+RUN"
                    />
                  </div>
                </>
              )}
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

              {ragStats && (
                <p className="auth-card__subtitle">
                  RAG: {ragStats.documents_ready}/{ragStats.documents_total} готово,
                  {' '}
                  {ragStats.chunks_total} фрагментів
                  {ragStats.documents_failed > 0
                    ? `, помилок: ${ragStats.documents_failed}`
                    : ''}
                  {ragStats.documents_failed > 0 && (
                    <>
                      {' '}
                      <button
                        type="button"
                        className="btn btn--ghost btn--sm"
                        onClick={handleReindexFailed}
                      >
                        Повторити всі failed
                      </button>
                    </>
                  )}
                </p>
              )}

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
                          <td className="table__actions">
                            {doc.status === 'failed' && (
                              <button
                                type="button"
                                className="btn btn--ghost btn--sm"
                                onClick={() => handleRetryDocument(doc.id)}
                              >
                                Повторити
                              </button>
                            )}
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
                  <th>Провайдер</th>
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
                    <td>{workspace.llm_provider === 'gemini' ? 'Gemini' : 'Ollama'}</td>
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

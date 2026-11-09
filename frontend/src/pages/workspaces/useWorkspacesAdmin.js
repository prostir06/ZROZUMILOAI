import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api/client';

export const emptyForm = {
  name: '',
  system_prompt: '',
  temperature: 0.7,
  user_ids: [],
  model_name: '',
  search_source: 'internal',
  meilisearch_url: '',
  meilisearch_api_key: '',
  meilisearch_index_prefix: 'tutor_',
  meilisearch_indexes: 'course_info, courseware_content',
  meilisearch_course_id: '',
  embed_greeting: '',
  embed_faq_questions: '',
};

export const parseIndexes = (value) => (value || '')
  .split(',')
  .map((item) => item.trim())
  .filter(Boolean);

export const formatIndexes = (indexes) => (indexes?.length ? indexes.join(', ') : '');

export function useWorkspacesAdmin() {
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
  const [widgetTokenCourseId, setWidgetTokenCourseId] = useState('');
  const [documents, setDocuments] = useState([]);
  const [uploadingDocument, setUploadingDocument] = useState(false);
  const [ragStats, setRagStats] = useState(null);

  const providerModels = models.filter(
    (model) => (model.provider || 'ollama') === 'ollama',
  );

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [workspacesData, usersData, modelsData] = await Promise.all([
        api.getWorkspaces(),
        api.getUsers(),
        api.getModels().catch((err) => {
          console.error('Failed to load models for workspaces form:', err);
          return { models: [] };
        }),
      ]);
      setWorkspaces(workspacesData);
      setUsers(usersData);
      setModels(modelsData.models || []);
    } catch (err) {
      console.error('Failed to load workspaces data:', err);
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
    setWidgetTokenCourseId('');
    setDocuments([]);
    setRagStats(null);
  };

  const loadWidgetTokens = async (workspaceId) => {
    try {
      const tokens = await api.getWidgetTokens(workspaceId);
      setWidgetTokens(tokens);
    } catch (err) {
      console.error('Failed to load widget tokens:', err);
      setError(err.message || 'Не вдалося завантажити віджет-токени');
      setWidgetTokens([]);
    }
  };

  const loadDocuments = async (workspaceId) => {
    try {
      const [docs, stats] = await Promise.all([
        api.getWorkspaceDocuments(workspaceId),
        api.getWorkspaceRagStats(workspaceId).catch((err) => {
          console.error('Failed to load RAG stats:', err);
          return null;
        }),
      ]);
      setDocuments(docs);
      setRagStats(stats);
    } catch (err) {
      console.error('Failed to load workspace documents:', err);
      setError(err.message || 'Не вдалося завантажити документи');
      setDocuments([]);
      setRagStats(null);
    }
  };

  // Polling processing status after async ingest
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

  const openEditForm = (workspace) => {
    setError('');
    setForm({
      name: workspace.name,
      system_prompt: workspace.system_prompt || '',
      temperature: workspace.temperature ?? 0.7,
      user_ids: workspace.users ? workspace.users.map((user) => user.id) : [],
      model_name: workspace.model_names?.[0] || '',
      search_source: workspace.search_source || 'internal',
      meilisearch_url: workspace.meilisearch_url || '',
      meilisearch_api_key: '',
      meilisearch_index_prefix: workspace.meilisearch_index_prefix || 'tutor_',
      meilisearch_indexes: formatIndexes(workspace.meilisearch_indexes) || 'course_info, courseware_content',
      meilisearch_course_id: workspace.meilisearch_course_id || '',
      embed_greeting: workspace.embed_greeting || '',
      embed_faq_questions: Array.isArray(workspace.embed_faq_questions)
        ? workspace.embed_faq_questions.join('\n')
        : '',
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

  const handleSave = async (event) => {
    if (event?.preventDefault) {
      event.preventDefault();
    }
    setError('');

    const payload = {
      name: form.name.trim(),
      system_prompt: form.system_prompt.trim(),
      temperature: form.temperature,
      user_ids: form.user_ids,
      model_names: form.model_name ? [form.model_name] : [],
      search_source: form.search_source,
      meilisearch_url: form.meilisearch_url.trim(),
      meilisearch_index_prefix: form.meilisearch_index_prefix.trim(),
      meilisearch_indexes: parseIndexes(form.meilisearch_indexes),
      meilisearch_course_id: form.meilisearch_course_id.trim(),
      embed_greeting: form.embed_greeting.trim(),
      embed_faq_questions: form.embed_faq_questions
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean)
        .slice(0, 8),
    };

    if (form.meilisearch_api_key.trim()) {
      payload.meilisearch_api_key = form.meilisearch_api_key.trim();
    }

    try {
      if (formMode === 'edit') {
        await api.updateWorkspace(editingId, payload);
      } else {
        await api.createWorkspace(payload);
      }
      resetForm();
      await loadData();
    } catch (err) {
      console.error('Failed to save workspace:', err);
      setError(err.message || 'Помилка збереження workspace');
    }
  };

  const handleDelete = async (workspaceId, name) => {
    if (typeof window !== 'undefined' && window.confirm && !window.confirm(`Видалити workspace "${name}"?`)) {
      return;
    }

    setError('');
    try {
      await api.deleteWorkspace(workspaceId);
      if (editingId === workspaceId) {
        resetForm();
      }
      await loadData();
    } catch (err) {
      console.error('Failed to delete workspace:', err);
      setError(err.message || 'Помилка видалення workspace');
    }
  };

  const handleCreateWidgetToken = async () => {
    if (!editingId) return;
    setError('');
    setNewWidgetToken('');
    try {
      const data = await api.createWidgetToken(
        editingId,
        widgetTokenLabel.trim(),
        widgetTokenCourseId.trim(),
      );
      setNewWidgetToken(data.token);
      setWidgetTokenLabel('');
      setWidgetTokenCourseId('');
      loadWidgetTokens(editingId);
    } catch (err) {
      console.error('Failed to create widget token:', err);
      setError(err.message || 'Помилка створення widget token');
    }
  };

  const handleDeleteWidgetToken = async (tokenId) => {
    if (!editingId) return;
    if (typeof window !== 'undefined' && window.confirm && !window.confirm('Видалити widget token? Віджет на сайті перестане працювати.')) {
      return;
    }
    setError('');
    try {
      await api.deleteWidgetToken(editingId, tokenId);
      loadWidgetTokens(editingId);
    } catch (err) {
      console.error('Failed to delete widget token:', err);
      setError(err.message || 'Помилка видалення token');
    }
  };

  const handleDocumentUpload = async (event) => {
    const file = event?.target?.files?.[0];
    if (!file || !editingId) return;

    setError('');
    setUploadingDocument(true);
    try {
      await api.uploadWorkspaceDocument(editingId, file);
      await loadDocuments(editingId);
    } catch (err) {
      console.error('Failed to upload workspace document:', err);
      setError(err.message || 'Помилка завантаження документа');
    } finally {
      setUploadingDocument(false);
      if (event?.target) {
        event.target.value = '';
      }
    }
  };

  const handleDeleteDocument = async (documentId, filename) => {
    if (!editingId) return;
    if (typeof window !== 'undefined' && window.confirm && !window.confirm(`Видалити документ "${filename}"?`)) {
      return;
    }
    setError('');
    try {
      await api.deleteWorkspaceDocument(editingId, documentId);
      loadDocuments(editingId);
    } catch (err) {
      console.error('Failed to delete workspace document:', err);
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
      console.error('Failed to retry document index:', err);
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
      console.error('Failed to reindex failed documents:', err);
      setError(err.message || 'Помилка reindex');
    }
  };

  const handleUploadMaterial = () => {
    if (typeof document !== 'undefined') {
      const section = document.getElementById('documents-rag-section');
      if (section) {
        section.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      const input = document.getElementById('workspace_document_upload');
      if (input) {
        input.focus();
      }
    }
  };

  const origin = typeof window !== 'undefined' ? window.location.origin : '';
  const widgetEmbedSnippet = newWidgetToken
    ? `<script src="${origin}/widget.js" data-widget-token="${newWidgetToken}" data-title="Підтримка"></script>`
    : '';

  return {
    workspaces,
    setWorkspaces,
    users,
    setUsers,
    models,
    setModels,
    providerModels,
    loading,
    setLoading,
    formMode,
    setFormMode,
    editingId,
    setEditingId,
    error,
    setError,
    form,
    setForm,
    widgetTokens,
    setWidgetTokens,
    newWidgetToken,
    setNewWidgetToken,
    widgetTokenLabel,
    setWidgetTokenLabel,
    widgetTokenCourseId,
    setWidgetTokenCourseId,
    widgetEmbedSnippet,
    documents,
    setDocuments,
    uploadingDocument,
    ragStats,
    loadData,
    loadWidgetTokens,
    loadDocuments,
    resetForm,
    closeForm: resetForm,
    openCreate: openCreateForm,
    openCreateForm,
    openEdit: openEditForm,
    openEditForm,
    handleSave,
    handleSubmit: handleSave,
    handleDelete,
    handleNameChange,
    handlePromptChange,
    handleTemperatureChange,
    toggleUserId,
    handleModelChange,
    handleCreateWidgetToken,
    handleDeleteWidgetToken,
    handleDocumentUpload,
    handleDeleteDocument,
    handleRetryDocument,
    handleReindexFailed,
    handleUploadMaterial,
  };
}

export default useWorkspacesAdmin;

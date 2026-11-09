import AnalyticsSection from './AnalyticsSection';
import DocumentsRagSection from './DocumentsRagSection';
import MeilisearchSection from './MeilisearchSection';
import WidgetTokensSection from './WidgetTokensSection';

export default function WorkspaceModal({
  formMode,
  editingId,
  form,
  setForm,
  users = [],
  providerModels = [],
  handleNameChange,
  handlePromptChange,
  handleTemperatureChange,
  toggleUserId,
  handleModelChange,
  handleSave,
  handleSubmit,
  closeForm,
  resetForm,
  onClose,
  widgetTokenLabel,
  setWidgetTokenLabel,
  widgetTokenCourseId,
  setWidgetTokenCourseId,
  handleCreateWidgetToken,
  onCreateWidgetToken,
  newWidgetToken,
  widgetEmbedSnippet,
  widgetTokens,
  handleDeleteWidgetToken,
  onDeleteWidgetToken,
  documents,
  ragStats,
  uploadingDocument,
  handleDocumentUpload,
  onDocumentUpload,
  handleRetryDocument,
  onRetryDocument,
  handleDeleteDocument,
  onDeleteDocument,
  handleReindexFailed,
  onReindexFailed,
  handleUploadMaterial,
  onUploadMaterial,
}) {
  if (!formMode) return null;

  const onFormSubmit = handleSubmit || handleSave;
  const onFormCancel = onClose || closeForm || resetForm;
  const onTokenCreate = onCreateWidgetToken || handleCreateWidgetToken;
  const onTokenDelete = onDeleteWidgetToken || handleDeleteWidgetToken;
  const onDocUpload = onDocumentUpload || handleDocumentUpload;
  const onDocRetry = onRetryDocument || handleRetryDocument;
  const onDocDelete = onDeleteDocument || handleDeleteDocument;
  const onReindex = onReindexFailed || handleReindexFailed;
  const onMaterialUpload = onUploadMaterial || handleUploadMaterial;

  return (
    <section className="section card">
      <h3 className="section__title">
        {formMode === 'edit' ? 'Редагування workspace' : 'Новий workspace'}
      </h3>
      <form onSubmit={onFormSubmit} className="form">
        <div className="form__group">
          <label htmlFor="workspace_name">Назва</label>
          <input
            id="workspace_name"
            value={form.name}
            onChange={handleNameChange}
            required
            maxLength={200}
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
            maxLength={8000}
            placeholder="Інструкції для моделі в цьому workspace..."
          />
        </div>

        <div className="form__group">
          <label htmlFor="workspace_embed_greeting">Привітання embed (опційно)</label>
          <input
            id="workspace_embed_greeting"
            value={form.embed_greeting}
            onChange={(e) => setForm((prev) => ({ ...prev, embed_greeting: e.target.value }))}
            placeholder="Вітаю! Я Помічник…"
          />
        </div>

        <div className="form__group">
          <label htmlFor="workspace_embed_faq">FAQ embed (по одному питанню на рядок)</label>
          <textarea
            id="workspace_embed_faq"
            value={form.embed_faq_questions}
            onChange={(e) => setForm((prev) => ({ ...prev, embed_faq_questions: e.target.value }))}
            rows={3}
            placeholder={"Як зареєструватися?\nЯк отримати сертифікат?"}
          />
        </div>

        <div className="form__group">
          <label htmlFor="workspace_temperature">
            Температура: {typeof form.temperature === 'number' ? form.temperature.toFixed(1) : form.temperature}
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
                      checked={form.user_ids?.includes(user.id)}
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
            {providerModels.length === 0 ? (
              <p className="empty-state">Немає встановлених моделей Ollama</p>
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

        <MeilisearchSection form={form} setForm={setForm} />

        <div className="form__actions">
          <button type="submit" className="btn btn--primary">
            {formMode === 'edit' ? 'Зберегти' : 'Створити'}
          </button>
          <button type="button" className="btn btn--ghost" onClick={onFormCancel}>
            Скасувати
          </button>
        </div>
      </form>

      {formMode === 'edit' && (
        <WidgetTokensSection
          widgetTokenLabel={widgetTokenLabel}
          setWidgetTokenLabel={setWidgetTokenLabel}
          widgetTokenCourseId={widgetTokenCourseId}
          setWidgetTokenCourseId={setWidgetTokenCourseId}
          onCreateToken={onTokenCreate}
          newWidgetToken={newWidgetToken}
          widgetEmbedSnippet={widgetEmbedSnippet}
          widgetTokens={widgetTokens}
          onDeleteToken={onTokenDelete}
        />
      )}

      {formMode === 'edit' && (
        <DocumentsRagSection
          documents={documents}
          ragStats={ragStats}
          uploadingDocument={uploadingDocument}
          onUpload={onDocUpload}
          onRetry={onDocRetry}
          onDelete={onDocDelete}
          onReindexFailed={onReindex}
        />
      )}

      {formMode === 'edit' && (
        <AnalyticsSection
          workspaceId={editingId}
          onUploadMaterial={onMaterialUpload}
        />
      )}
    </section>
  );
}

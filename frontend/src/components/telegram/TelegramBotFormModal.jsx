export default function TelegramBotFormModal({
  formMode,
  form,
  workspaces,
  saving,
  onClose,
  onChange,
  onSubmit,
}) {
  if (!formMode) return null;

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="bot-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal">
        <div className="modal__header">
          <h3 id="bot-modal-title" className="modal__title">
            {formMode === 'edit' ? 'Редагувати бота' : 'Додати телеграм-бота'}
          </h3>
          <button
            type="button"
            className="modal__close"
            onClick={onClose}
            aria-label="Закрити"
          >
            ✕
          </button>
        </div>
        <form
          onSubmit={(e) => {
            onSubmit(e).catch((err) => {
              console.error('Failed to submit telegram bot form:', err);
            });
          }}
          className="form"
        >
          <div className="modal__body">
            <div className="form__group">
              <label htmlFor="bot_name">Назва</label>
              <input
                id="bot_name"
                name="name"
                value={form.name}
                onChange={onChange}
                required
                maxLength={200}
                placeholder="Напр. Бот підтримки студентів"
              />
            </div>

            <div className="form__group">
              <label htmlFor="bot_token">Токен бота</label>
              <input
                id="bot_token"
                name="token"
                type="password"
                value={form.token}
                onChange={onChange}
                required={formMode === 'create'}
                placeholder={
                  formMode === 'edit'
                    ? 'Залиште порожнім, щоб не змінювати'
                    : '123456789:ABCdefGHIjklMNOpqrsTUVwxyz'
                }
              />
              <small className="form__help">
                {formMode === 'edit'
                  ? 'Залиште поле порожнім, щоб зберегти поточний токен.'
                  : 'Токен від @BotFather у форматі 123456:ABC-DEF...'}
              </small>
            </div>

            <div className="form__group">
              <label htmlFor="bot_workspace">Workspace</label>
              <select
                id="bot_workspace"
                name="workspace"
                value={form.workspace}
                onChange={onChange}
              >
                <option value="">Не привʼязано</option>
                {workspaces.map((ws) => (
                  <option key={ws.id} value={ws.id}>
                    {ws.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="form__group">
              <label className="checkbox-label" htmlFor="bot_is_active">
                <input
                  id="bot_is_active"
                  name="is_active"
                  type="checkbox"
                  checked={form.is_active}
                  onChange={onChange}
                />
                <span>Активний</span>
              </label>
            </div>
          </div>

          <div className="modal__footer">
            <button
              type="button"
              className="btn btn--ghost"
              onClick={onClose}
              disabled={saving}
            >
              Скасувати
            </button>
            <button
              type="submit"
              className="btn btn--primary"
              disabled={saving}
            >
              {saving ? 'Збереження...' : formMode === 'edit' ? 'Зберегти' : 'Створити'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

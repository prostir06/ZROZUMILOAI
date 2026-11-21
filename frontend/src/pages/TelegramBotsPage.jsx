import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client.js';
import {
  createTelegramBot,
  deleteTelegramBot,
  getTelegramBots,
  updateTelegramBot,
  verifyTelegramBot,
} from '../api/telegramBots.js';
import TelegramBotFormModal from '../components/telegram/TelegramBotFormModal.jsx';
import TelegramBotsTable from '../components/telegram/TelegramBotsTable.jsx';

export const emptyForm = {
  name: '',
  token: '',
  workspace: '',
  is_active: true,
};

export function useTelegramBots({
  initialBots = null,
  initialWorkspaces = null,
  initialFormMode = null,
  initialEditingBotId = null,
  initialForm = null,
} = {}) {
  const [bots, setBots] = useState(initialBots || []);
  const [workspaces, setWorkspaces] = useState(initialWorkspaces || []);
  const [loading, setLoading] = useState(initialBots === null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState(null);
  const [formMode, setFormMode] = useState(initialFormMode);
  const [editingBotId, setEditingBotId] = useState(initialEditingBotId);
  const [form, setForm] = useState(initialForm || emptyForm);
  const [saving, setSaving] = useState(false);
  const [verifyingId, setVerifyingId] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [fetchedBots, fetchedWorkspaces] = await Promise.all([
        getTelegramBots(),
        api.getWorkspaces().catch((err) => {
          console.error('Failed to load workspaces for telegram bots form:', err);
          return [];
        }),
      ]);
      setBots(fetchedBots);
      setWorkspaces(fetchedWorkspaces);
      return { bots: fetchedBots, workspaces: fetchedWorkspaces };
    } catch (err) {
      console.error('Failed to load telegram bots:', err);
      setError(err.message || 'Не вдалося завантажити телеграм-ботів');
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (initialBots === null) {
      // Помилка вже залогована та збережена у стані error всередині loadData.
      loadData().catch(() => {});
    }
  }, [initialBots, loadData]);

  const openCreateModal = () => {
    setForm(emptyForm);
    setFormMode('create');
    setEditingBotId(null);
    setError('');
    setNotice(null);
  };

  const openEditModal = (bot) => {
    setForm({
      name: bot.name || '',
      token: '',
      workspace: bot.workspace != null ? String(bot.workspace) : '',
      is_active: bot.is_active ?? true,
    });
    setFormMode('edit');
    setEditingBotId(bot.id);
    setError('');
    setNotice(null);
  };

  const closeModal = () => {
    setFormMode(null);
    setEditingBotId(null);
    setForm(emptyForm);
    setSaving(false);
  };

  const handleFormChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleSubmit = async (e, customData = null) => {
    if (e && e.preventDefault) e.preventDefault();
    setError('');
    setNotice(null);

    const activeForm = customData?.form || form;
    const activeMode = customData?.mode || formMode;
    const activeEditingId = customData?.editingId ?? editingBotId;

    const name = (activeForm.name || '').trim();
    if (!name) {
      const msg = 'Введіть назву бота';
      setError(msg);
      return { error: msg };
    }

    setSaving(true);
    try {
      const workspaceId = activeForm.workspace !== '' && activeForm.workspace !== null
        ? Number(activeForm.workspace)
        : null;

      if (activeMode === 'create') {
        const token = (activeForm.token || '').trim();
        if (!token) {
          const msg = 'Введіть токен бота';
          setError(msg);
          setSaving(false);
          return { error: msg };
        }

        const newBot = await createTelegramBot({
          name,
          token,
          workspace: workspaceId,
          is_active: Boolean(activeForm.is_active),
        });

        setBots((prev) => [...prev, newBot]);
        setNotice({
          type: 'success',
          message: `Бота "${newBot.name}" успішно створено`,
        });
        closeModal();
        return newBot;
      } else if (activeMode === 'edit') {
        const payload = {
          name,
          workspace: workspaceId,
          is_active: Boolean(activeForm.is_active),
        };
        if (activeForm.token && activeForm.token.trim()) {
          payload.token = activeForm.token.trim();
        }

        const updatedBot = await updateTelegramBot(activeEditingId, payload);
        setBots((prev) => prev.map((b) => (b.id === activeEditingId ? updatedBot : b)));
        setNotice({
          type: 'success',
          message: `Бота "${updatedBot.name}" оновлено`,
        });
        closeModal();
        return updatedBot;
      }
    } catch (err) {
      console.error('Failed to save telegram bot:', err);
      const msg = err.message || 'Помилка збереження бота';
      setError(msg);
      return { error: msg };
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (botId, botName) => {
    const confirmed = typeof window !== 'undefined' && window.confirm
      ? window.confirm(`Видалити телеграм-бота "${botName}"?`)
      : true;

    if (!confirmed) return false;

    setError('');
    setNotice(null);
    try {
      await deleteTelegramBot(botId);
      setBots((prev) => prev.filter((b) => b.id !== botId));
      setNotice({
        type: 'success',
        message: `Бота "${botName}" видалено`,
      });
      if (editingBotId === botId) {
        closeModal();
      }
      return true;
    } catch (err) {
      console.error('Failed to delete telegram bot:', err);
      const msg = err.message || 'Не вдалося видалити бота';
      setError(msg);
      return { error: msg };
    }
  };

  const handleVerify = async (botId) => {
    setVerifyingId(botId);
    setError('');
    setNotice(null);
    try {
      const verifiedBot = await verifyTelegramBot(botId);
      setBots((prev) => prev.map((b) => (b.id === botId ? verifiedBot : b)));
      setNotice({
        type: 'success',
        message: `Токен бота "${verifiedBot.name}" перевірено (${verifiedBot.bot_username ? `@${verifiedBot.bot_username}` : 'успішно'})`,
      });
      return verifiedBot;
    } catch (err) {
      console.error('Failed to verify telegram bot token:', err);
      const msg = err.message || 'Не вдалося перевірити токен телеграм-бота';
      setError(msg);
      return { error: msg };
    } finally {
      setVerifyingId(null);
    }
  };

  return {
    bots,
    setBots,
    workspaces,
    setWorkspaces,
    loading,
    error,
    setError,
    notice,
    setNotice,
    formMode,
    editingBotId,
    form,
    setForm,
    saving,
    verifyingId,
    loadData,
    openCreateModal,
    openEditModal,
    closeModal,
    handleFormChange,
    handleSubmit,
    handleDelete,
    handleVerify,
  };
}

export default function TelegramBotsPage({
  initialBots = null,
  initialWorkspaces = null,
  initialFormMode = null,
  initialEditingBotId = null,
  initialForm = null,
} = {}) {
  const {
    bots,
    workspaces,
    loading,
    error,
    notice,
    formMode,
    form,
    saving,
    verifyingId,
    openCreateModal,
    openEditModal,
    closeModal,
    handleFormChange,
    handleSubmit,
    handleDelete,
    handleVerify,
  } = useTelegramBots({
    initialBots,
    initialWorkspaces,
    initialFormMode,
    initialEditingBotId,
    initialForm,
  });

  return (
    <div className="page">
      <header className="page__header page__header--row">
        <div>
          <h2>Телеграм-боти</h2>
          <p>Керування підключеними ботами Telegram та привʼязка до робочих просторів</p>
        </div>
        <button
          type="button"
          className="btn btn--primary"
          onClick={formMode ? closeModal : openCreateModal}
        >
          <span aria-hidden="true">+</span> {formMode === 'create' ? 'Скасувати' : 'Додати бота'}
        </button>
      </header>

      {error && (
        <div className="alert alert--error" role="alert">
          {error}
        </div>
      )}

      {notice && (
        <div className={`alert alert--${notice.type || 'success'}`} role="status">
          {notice.message}
        </div>
      )}

      <TelegramBotFormModal
        formMode={formMode}
        form={form}
        workspaces={workspaces}
        saving={saving}
        onClose={closeModal}
        onChange={handleFormChange}
        onSubmit={handleSubmit}
      />

      <TelegramBotsTable
        bots={bots}
        loading={loading}
        verifyingId={verifyingId}
        onVerify={handleVerify}
        onEdit={openEditModal}
        onDelete={handleDelete}
      />
    </div>
  );
}

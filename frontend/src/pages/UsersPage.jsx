import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';

const emptyForm = {
  username: '',
  email: '',
  password: '',
  first_name: '',
  last_name: '',
  is_staff: false,
};

function UsersPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [formMode, setFormMode] = useState(null);
  const [editingUserId, setEditingUserId] = useState(null);
  const [error, setError] = useState('');
  const [createdApiKey, setCreatedApiKey] = useState('');
  const [form, setForm] = useState(emptyForm);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getUsers();
      setUsers(data);
    } catch {
      setError('Не вдалося завантажити користувачів');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const resetForm = () => {
    setForm(emptyForm);
    setFormMode(null);
    setEditingUserId(null);
  };

  const openCreateForm = () => {
    setCreatedApiKey('');
    setError('');
    setForm(emptyForm);
    setFormMode('create');
    setEditingUserId(null);
  };

  const openEditForm = (user) => {
    setCreatedApiKey('');
    setError('');
    setForm({
      username: user.username,
      email: user.email,
      password: '',
      first_name: user.first_name || '',
      last_name: user.last_name || '',
      is_staff: user.is_staff,
    });
    setFormMode('edit');
    setEditingUserId(user.id);
  };

  const handleChange = (event) => {
    const { name, value, type, checked } = event.target;
    setForm({
      ...form,
      [name]: type === 'checkbox' ? checked : value,
    });
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setCreatedApiKey('');

    try {
      if (formMode === 'edit') {
        const payload = {
          username: form.username,
          email: form.email,
          first_name: form.first_name,
          last_name: form.last_name,
          is_staff: form.is_staff,
        };
        if (form.password) {
          payload.password = form.password;
        }
        await api.updateUser(editingUserId, payload);
      } else {
        const created = await api.createUser(form);
        setCreatedApiKey(created.api_key || '');
      }
      resetForm();
      loadUsers();
    } catch (err) {
      setError(err.message || 'Помилка збереження користувача');
    }
  };

  const handleDelete = async (userId, username) => {
    if (!window.confirm(`Видалити користувача "${username}"?`)) return;

    setError('');
    try {
      await api.deleteUser(userId);
      if (editingUserId === userId) {
        resetForm();
      }
      loadUsers();
    } catch (err) {
      setError(err.message || 'Помилка видалення користувача');
    }
  };

  const handleCopyKey = async (key) => {
    try {
      await navigator.clipboard.writeText(key);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <div className="page">
      <header className="page__header page__header--row">
        <div>
          <h2>Користувачі</h2>
          <p>Керування обліковими записами</p>
        </div>
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => (formMode === 'create' ? resetForm() : openCreateForm())}
        >
          {formMode === 'create' ? 'Скасувати' : 'Додати користувача'}
        </button>
      </header>

      {error && <div className="alert alert--error" role="alert">{error}</div>}

      {createdApiKey && (
        <div className="alert alert--success api-key-alert" role="status">
          <p><strong>API ключ створено.</strong> Збережіть його — більше не буде показано:</p>
          <code className="api-key">{createdApiKey}</code>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            onClick={() => handleCopyKey(createdApiKey)}
          >
            Копіювати
          </button>
        </div>
      )}

      {formMode && (
        <section className="section card">
          <h3 className="section__title">
            {formMode === 'edit' ? 'Редагування користувача' : 'Новий користувач'}
          </h3>
          <form onSubmit={handleSubmit} className="form">
            <div className="form__row">
              <div className="form__group">
                <label htmlFor="user_username">Ім&apos;я користувача</label>
                <input
                  id="user_username"
                  name="username"
                  value={form.username}
                  onChange={handleChange}
                  required
                />
              </div>
              <div className="form__group">
                <label htmlFor="user_email">Email</label>
                <input
                  id="user_email"
                  name="email"
                  type="email"
                  value={form.email}
                  onChange={handleChange}
                  required
                />
              </div>
            </div>

            <div className="form__row">
              <div className="form__group">
                <label htmlFor="user_first_name">Ім&apos;я</label>
                <input
                  id="user_first_name"
                  name="first_name"
                  value={form.first_name}
                  onChange={handleChange}
                />
              </div>
              <div className="form__group">
                <label htmlFor="user_last_name">Прізвище</label>
                <input
                  id="user_last_name"
                  name="last_name"
                  value={form.last_name}
                  onChange={handleChange}
                />
              </div>
            </div>

            <div className="form__group">
              <label htmlFor="user_password">
                {formMode === 'edit' ? 'Новий пароль (необов\'язково)' : 'Пароль'}
              </label>
              <input
                id="user_password"
                name="password"
                type="password"
                value={form.password}
                onChange={handleChange}
                required={formMode === 'create'}
                minLength={form.password ? 8 : undefined}
              />
            </div>

            <label className="checkbox">
              <input
                type="checkbox"
                name="is_staff"
                checked={form.is_staff}
                onChange={handleChange}
                disabled={formMode === 'edit' && editingUserId === currentUser?.id}
              />
              Адміністратор
            </label>

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
        ) : (
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Користувач</th>
                  <th>Email</th>
                  <th>Ім&apos;я</th>
                  <th>Роль</th>
                  <th>API ключ</th>
                  <th>Дії</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td><strong>{u.username}</strong></td>
                    <td>{u.email}</td>
                    <td>{[u.first_name, u.last_name].filter(Boolean).join(' ') || '—'}</td>
                    <td>
                      <span className={`badge ${u.is_staff ? 'badge--admin' : ''}`}>
                        {u.is_staff ? 'Адмін' : 'Користувач'}
                      </span>
                    </td>
                    <td>
                      <code className="api-key api-key--muted">
                        {u.api_key_prefix || '—'}
                      </code>
                    </td>
                    <td className="table__actions">
                      <button
                        type="button"
                        className="btn btn--ghost btn--sm"
                        onClick={() => openEditForm(u)}
                      >
                        Редагувати
                      </button>
                      <button
                        type="button"
                        className="btn btn--danger btn--sm"
                        disabled={u.id === currentUser?.id}
                        onClick={() => handleDelete(u.id, u.username)}
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

export default UsersPage;

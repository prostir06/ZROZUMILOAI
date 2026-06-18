import { useState } from 'react';
import { api } from '../api/client';

function PasswordPage() {
  const [form, setForm] = useState({
    current_password: '',
    new_password: '',
    new_password_confirm: '',
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      await api.changePassword(form);
      setSuccess('Пароль успішно змінено');
      setForm({
        current_password: '',
        new_password: '',
        new_password_confirm: '',
      });
    } catch (err) {
      setError(err.message || 'Не вдалося змінити пароль');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <header className="page__header">
        <h2>Зміна пароля</h2>
        <p>Оновіть пароль для свого облікового запису</p>
      </header>

      {error && <div className="alert alert--error" role="alert">{error}</div>}
      {success && <div className="alert alert--success" role="status">{success}</div>}

      <section className="section card" style={{ maxWidth: '480px' }}>
        <form onSubmit={handleSubmit} className="form">
          <div className="form__group">
            <label htmlFor="current_password">Поточний пароль</label>
            <input
              id="current_password"
              name="current_password"
              type="password"
              value={form.current_password}
              onChange={handleChange}
              required
              autoComplete="current-password"
            />
          </div>

          <div className="form__group">
            <label htmlFor="new_password">Новий пароль</label>
            <input
              id="new_password"
              name="new_password"
              type="password"
              value={form.new_password}
              onChange={handleChange}
              required
              minLength={8}
              autoComplete="new-password"
            />
          </div>

          <div className="form__group">
            <label htmlFor="new_password_confirm">Підтвердження пароля</label>
            <input
              id="new_password_confirm"
              name="new_password_confirm"
              type="password"
              value={form.new_password_confirm}
              onChange={handleChange}
              required
              minLength={8}
              autoComplete="new-password"
            />
          </div>

          <div className="form__actions">
            <button type="submit" className="btn btn--primary" disabled={loading}>
              {loading ? 'Збереження...' : 'Змінити пароль'}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

export default PasswordPage;

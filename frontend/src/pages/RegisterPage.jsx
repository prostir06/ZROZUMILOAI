import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';

function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    password_confirm: '',
    first_name: '',
    last_name: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [apiKey, setApiKey] = useState('');

  const handleChange = (event) => {
    setForm({ ...form, [event.target.name]: event.target.value });
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setLoading(true);
    setApiKey('');

    try {
      const data = await api.register(form);
      if (data.api_key) {
        setApiKey(data.api_key);
      } else {
        navigate('/login');
      }
    } catch {
      setError('Перевірте правильність введених даних');
    } finally {
      setLoading(false);
    }
  };

  if (apiKey) {
    return (
      <div className="auth-page">
        <div className="auth-card auth-card--wide">
          <h2 className="auth-card__title">Реєстрація успішна</h2>
          <p className="auth-card__subtitle">
            Збережіть API ключ — він більше не буде показаний
          </p>
          <code className="api-key">{apiKey}</code>
          <button type="button" className="btn btn--primary btn--full" onClick={() => navigate('/login')}>
            Перейти до входу
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-card auth-card--wide">
        <h2 className="auth-card__title">Реєстрація</h2>
        <p className="auth-card__subtitle">Створіть обліковий запис</p>

        {error && <div className="alert alert--error" role="alert">{error}</div>}

        <form onSubmit={handleSubmit} className="form">
          <div className="form__row">
            <div className="form__group">
              <label htmlFor="first_name">Ім&apos;я</label>
              <input
                id="first_name"
                name="first_name"
                type="text"
                value={form.first_name}
                onChange={handleChange}
              />
            </div>
            <div className="form__group">
              <label htmlFor="last_name">Прізвище</label>
              <input
                id="last_name"
                name="last_name"
                type="text"
                value={form.last_name}
                onChange={handleChange}
              />
            </div>
          </div>

          <div className="form__group">
            <label htmlFor="username">Ім&apos;я користувача</label>
            <input
              id="username"
              name="username"
              type="text"
              value={form.username}
              onChange={handleChange}
              required
            />
          </div>

          <div className="form__group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              name="email"
              type="email"
              value={form.email}
              onChange={handleChange}
              required
            />
          </div>

          <div className="form__row">
            <div className="form__group">
              <label htmlFor="password">Пароль</label>
              <input
                id="password"
                name="password"
                type="password"
                value={form.password}
                onChange={handleChange}
                required
                minLength={8}
              />
            </div>
            <div className="form__group">
              <label htmlFor="password_confirm">Підтвердження</label>
              <input
                id="password_confirm"
                name="password_confirm"
                type="password"
                value={form.password_confirm}
                onChange={handleChange}
                required
                minLength={8}
              />
            </div>
          </div>

          <button type="submit" className="btn btn--primary btn--full" disabled={loading}>
            {loading ? 'Реєстрація...' : 'Зареєструватися'}
          </button>
        </form>

        <p className="auth-card__footer">
          Вже є обліковий запис? <Link to="/login">Увійти</Link>
        </p>
      </div>
    </div>
  );
}

export default RegisterPage;

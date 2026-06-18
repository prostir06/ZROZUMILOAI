import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';

function formatBytes(bytes) {
  if (!bytes) return '—';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let size = bytes;
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024;
    i += 1;
  }
  return `${size.toFixed(1)} ${units[i]}`;
}

function DashboardPage() {
  const { user } = useAuth();
  const [health, setHealth] = useState(null);
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [healthData, modelsData] = await Promise.all([
          api.getOllamaHealth(),
          api.getModels().catch(() => ({ models: [] })),
        ]);
        setHealth(healthData);
        setModels(modelsData.models || []);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) {
    return <div className="page-loading"><div className="spinner" /></div>;
  }

  return (
    <div className="page">
      <header className="page__header">
        <h2>Панель керування</h2>
        <p>Вітаємо, {user?.first_name || user?.username}!</p>
      </header>

      <div className="grid grid--cards">
        <article className="card">
          <h3 className="card__title">Статус Ollama</h3>
          <div className={`status-badge ${health?.connected ? 'status-badge--ok' : 'status-badge--error'}`}>
            {health?.connected ? 'Підключено' : 'Недоступно'}
          </div>
          <p className="card__meta">{health?.base_url}</p>
        </article>

        <article className="card">
          <h3 className="card__title">Моделі</h3>
          <p className="card__value">{models.length}</p>
          <Link to="/admin/models" className="card__link">Керувати моделями →</Link>
        </article>

        <article className="card">
          <h3 className="card__title">Чат</h3>
          <p className="card__text">Спілкуйтеся з AI-помічником</p>
          <Link to="/chat" className="card__link">Відкрити чат →</Link>
        </article>
      </div>

      {models.length > 0 && (
        <section className="section">
          <h3 className="section__title">Встановлені моделі</h3>
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Назва</th>
                  <th>Розмір</th>
                  <th>Оновлено</th>
                </tr>
              </thead>
              <tbody>
                {models.slice(0, 5).map((model) => (
                  <tr key={model.name}>
                    <td>{model.name}</td>
                    <td>{formatBytes(model.size)}</td>
                    <td>{new Date(model.modified_at).toLocaleDateString('uk-UA')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

export default DashboardPage;

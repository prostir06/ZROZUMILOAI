/**
 * Адмін-дашборд: статуси API/Ollama, моделі, handoff.
 * Семантика HTML5: header + article cards + section таблиці.
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';

/** Людинозрозумілий розмір файлу моделі. */
function formatBytes(bytes) {
  try {
    if (!bytes || Number.isNaN(Number(bytes))) {
      return '—';
    }
    const units = ['B', 'KB', 'MB', 'GB'];
    let i = 0;
    let size = Number(bytes);
    while (size >= 1024 && i < units.length - 1) {
      size /= 1024;
      i += 1;
    }
    return `${size.toFixed(1)} ${units[i]}`;
  } catch {
    return '—';
  }
}

/** Безпечний JSON з fetch (не кидає при порожньому тілі). */
async function fetchJsonSafe(url) {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      return null;
    }
    return await response.json();
  } catch {
    return null;
  }
}

function DashboardPage() {
  const { user } = useAuth();
  const [health, setHealth] = useState(null);
  const [apiHealth, setApiHealth] = useState(null);
  const [models, setModels] = useState([]);
  const [handoffCount, setHandoffCount] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoadError('');
      try {
        const [healthData, modelsData, apiHealthData, logsData] = await Promise.all([
          api.getOllamaHealth().catch(() => null),
          api.getModels().catch(() => ({ models: [] })),
          fetchJsonSafe('/api/health/'),
          api.getWorkspaceChatLogs({ needsHandoff: true, limit: 1 })
            .catch(() => ({ count: null })),
        ]);
        if (cancelled) {
          return;
        }
        setHealth(healthData);
        setModels(Array.isArray(modelsData?.models) ? modelsData.models : []);
        setApiHealth(apiHealthData);
        setHandoffCount(
          typeof logsData?.count === 'number' ? logsData.count : null,
        );
      } catch (err) {
        if (!cancelled) {
          setLoadError(err?.message || 'Не вдалося завантажити панель');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="page-loading" role="status" aria-live="polite">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="page">
      <header className="page__header">
        <h2>Панель керування</h2>
        <p>Вітаємо, {user?.first_name || user?.username}!</p>
      </header>

      {loadError && (
        <div className="alert alert--error" role="alert">
          {loadError}
        </div>
      )}

      <div className="grid grid--cards">
        <article className="card">
          <h3 className="card__title">API / БД</h3>
          <div
            className={`status-badge ${apiHealth?.status === 'ok' ? 'status-badge--ok' : 'status-badge--error'}`}
          >
            {apiHealth?.status === 'ok' ? 'OK' : (apiHealth?.status || 'Невідомо')}
          </div>
          <p className="card__meta">
            DB: {apiHealth?.database || '—'}
            {' · '}
            Cache: {apiHealth?.cache || '—'}
          </p>
        </article>

        <article className="card">
          <h3 className="card__title">Статус Ollama</h3>
          <div
            className={`status-badge ${health?.connected ? 'status-badge--ok' : 'status-badge--error'}`}
          >
            {health?.connected ? 'Підключено' : 'Недоступно'}
          </div>
          <p className="card__meta">{health?.base_url || '—'}</p>
        </article>

        <article className="card">
          <h3 className="card__title">Моделі</h3>
          <p className="card__value">{models.length}</p>
          <Link to="/admin/models" className="card__link">Керувати моделями →</Link>
        </article>

        <article className="card">
          <h3 className="card__title">Handoff</h3>
          <p className="card__value">{handoffCount ?? '—'}</p>
          <Link to="/admin/chats" className="card__link">Chats Info →</Link>
        </article>

        <article className="card">
          <h3 className="card__title">Чат</h3>
          <p className="card__text">Спілкуйтеся з AI-помічником</p>
          <Link to="/" className="card__link">Відкрити чат →</Link>
        </article>
      </div>

      {models.length > 0 && (
        <section className="section" aria-labelledby="dashboard-models-title">
          <h3 id="dashboard-models-title" className="section__title">
            Встановлені моделі
          </h3>
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Назва</th>
                  <th scope="col">Розмір</th>
                  <th scope="col">Оновлено</th>
                </tr>
              </thead>
              <tbody>
                {models.slice(0, 5).map((model) => (
                  <tr key={model.name}>
                    <td>{model.name}</td>
                    <td>{formatBytes(model.size)}</td>
                    <td>
                      {model.modified_at
                        ? new Date(model.modified_at).toLocaleDateString('uk-UA')
                        : '—'}
                    </td>
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

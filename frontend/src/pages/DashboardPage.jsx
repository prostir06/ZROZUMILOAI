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
  const numericBytes = Number(bytes);
  if (!bytes || !Number.isFinite(numericBytes) || numericBytes < 0) {
    return '—';
  }
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let size = numericBytes;
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024;
    i += 1;
  }
  return `${size.toFixed(1)} ${units[i]}`;
}

/** Безпечний JSON з fetch (не кидає при порожньому тілі). */
async function fetchJsonSafe(url) {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      return null;
    }
    return await response.json();
  } catch (err) {
    console.warn(`fetchJsonSafe failed for ${url}:`, err);
    return null;
  }
}

function DashboardPage() {
  const { user } = useAuth();
  const [health, setHealth] = useState(null);
  const [apiHealth, setApiHealth] = useState(null);
  const [systemDetails, setSystemDetails] = useState(null);
  const [models, setModels] = useState([]);
  const [handoffCount, setHandoffCount] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoadError('');
      try {
        const [
          healthData,
          modelsData,
          apiHealthData,
          logsData,
          detailsData,
        ] = await Promise.all([
          api.getOllamaHealth().catch((err) => {
            console.error('Failed to load Ollama health for dashboard:', err);
            return null;
          }),
          api.getModels().catch((err) => {
            console.error('Failed to load models list for dashboard:', err);
            return { models: [] };
          }),
          fetchJsonSafe('/api/health/'),
          api.getWorkspaceChatLogs({ needsHandoff: true, limit: 1 })
            .catch((err) => {
              console.error('Failed to load handoff count for dashboard:', err);
              return { count: null };
            }),
          api.getSystemHealthDetails().catch((err) => {
            console.error('Failed to load system health details:', err);
            return null;
          }),
        ]);
        if (cancelled) {
          return;
        }
        setHealth(healthData);
        setModels(Array.isArray(modelsData?.models) ? modelsData.models : []);
        setApiHealth(apiHealthData);
        setSystemDetails(detailsData);
        setHandoffCount(
          typeof logsData?.count === 'number' ? logsData.count : null,
        );
      } catch (err) {
        console.error('Failed to load dashboard data:', err);
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

        {(() => {
          const celery = systemDetails?.celery;
          const celeryStatus = celery?.status;
          const celeryBadgeClass = celeryStatus === 'ok'
            ? 'status-badge--ok'
            : celeryStatus === 'eager'
              ? 'status-badge--warn'
              : 'status-badge--error';
          const celeryLabel = celeryStatus === 'ok'
            ? 'Активний'
            : celeryStatus === 'eager'
              ? 'Синхронний'
              : celeryStatus === 'error'
                ? 'Недоступний'
                : 'Невідомо';
          const celeryMeta = celeryStatus === 'eager'
            ? 'Локальний eager-режим'
            : `Воркерів: ${celery?.workers ?? '—'}`;

          return (
            <article className="card" data-testid="dashboard-card-celery">
              <h3 className="card__title">Celery Worker</h3>
              <div className={`status-badge ${celeryBadgeClass}`}>{celeryLabel}</div>
              <p className="card__meta">{celeryMeta}</p>
            </article>
          );
        })()}

        {(() => {
          const poller = systemDetails?.telegram_poller;
          const pollerStatus = poller?.status;
          const pollerBadgeClass = pollerStatus === 'ok'
            ? 'status-badge--ok'
            : pollerStatus === 'stale'
              ? 'status-badge--warn'
              : 'status-badge--error';
          const pollerLabel = pollerStatus === 'ok'
            ? 'Активний'
            : pollerStatus === 'stale'
              ? 'Затримка'
              : pollerStatus === 'offline'
                ? 'Офлайн'
                : 'Невідомо';

          return (
            <article className="card" data-testid="dashboard-card-poller">
              <h3 className="card__title">Telegram Poller</h3>
              <div className={`status-badge ${pollerBadgeClass}`}>{pollerLabel}</div>
              <p className="card__meta">
                Активних ботів: {poller?.active_bots ?? '—'}
                {' · '}
                Помилок: {poller?.bots_with_errors ?? '—'}
              </p>
              <Link to="/admin/telegram-bots" className="card__link">Телеграм-боти →</Link>
            </article>
          );
        })()}

        {(() => {
          const rag = systemDetails?.rag;
          const failedCount = rag?.failed ?? 0;
          const processingCount = rag?.processing ?? 0;
          const ragBadgeClass = !rag
            ? 'status-badge--error'
            : failedCount > 0
              ? 'status-badge--error'
              : processingCount > 0
                ? 'status-badge--warn'
                : 'status-badge--ok';
          const ragLabel = !rag
            ? 'Невідомо'
            : failedCount > 0
              ? `Помилки: ${failedCount}`
              : processingCount > 0
                ? `В обробці: ${processingCount}`
                : 'OK';

          return (
            <article className="card" data-testid="dashboard-card-rag">
              <h3 className="card__title">RAG Індексація</h3>
              <div className={`status-badge ${ragBadgeClass}`}>{ragLabel}</div>
              <p className="card__meta">
                {rag
                  ? `Готово: ${rag.ready ?? 0} / ${rag.total_documents ?? 0} · В обробці: ${processingCount}`
                  : 'Готово: —'}
              </p>
              <Link to="/admin/workspaces" className="card__link">Робочі простори →</Link>
            </article>
          );
        })()}
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

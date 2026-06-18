import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';

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

const POPULAR_MODELS = [
  'llama3.2',
  'llama3.1',
  'mistral',
  'gemma2',
  'phi3',
  'qwen2.5',
  'codellama',
];

function ModelsPage() {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pullName, setPullName] = useState('');
  const [pulling, setPulling] = useState(false);
  const [pullProgress, setPullProgress] = useState('');
  const [error, setError] = useState('');

  const loadModels = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.getModels();
      setModels(data.models || []);
    } catch (err) {
      setError(err.message);
      setModels([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadModels();
  }, [loadModels]);

  const handlePull = (name) => {
    const modelName = name || pullName.trim();
    if (!modelName || pulling) return;

    setPulling(true);
    setPullProgress('Початок завантаження...');
    setError('');

    api.pullModelStream(modelName, (data) => {
      if (data.error) {
        setError(data.error);
        setPulling(false);
        return;
      }
      if (data.status) {
        setPullProgress(data.status);
      }
      if (data.completed && data.total) {
        const pct = Math.round((data.completed / data.total) * 100);
        setPullProgress(`${data.status || 'Завантаження'}: ${pct}%`);
      }
      if (data.status === 'done') {
        setPulling(false);
        setPullProgress('');
        setPullName('');
        loadModels();
      }
    });
  };

  const handleDelete = async (name) => {
    if (!window.confirm(`Видалити модель "${name}"?`)) return;

    try {
      await api.deleteModel(name);
      loadModels();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="page">
      <header className="page__header">
        <h2>Моделі Ollama</h2>
        <p>Керуйте встановленими моделями або завантажуйте нові</p>
      </header>

      <section className="section">
        <h3 className="section__title">Завантажити модель</h3>
        <div className="pull-form">
          <input
            type="text"
            value={pullName}
            onChange={(e) => setPullName(e.target.value)}
            placeholder="Назва моделі, напр. llama3.2"
            disabled={pulling}
            className="input"
          />
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => handlePull()}
            disabled={pulling || !pullName.trim()}
          >
            {pulling ? 'Завантаження...' : 'Завантажити'}
          </button>
        </div>

        {pullProgress && (
          <div className="progress-bar" role="progressbar">
            <span>{pullProgress}</span>
          </div>
        )}

        <div className="model-tags">
          <span className="model-tags__label">Популярні:</span>
          {POPULAR_MODELS.map((name) => (
            <button
              key={name}
              type="button"
              className="tag"
              onClick={() => handlePull(name)}
              disabled={pulling}
            >
              {name}
            </button>
          ))}
        </div>
      </section>

      {error && <div className="alert alert--error" role="alert">{error}</div>}

      <section className="section">
        <div className="section__header">
          <h3 className="section__title">Встановлені моделі</h3>
          <button type="button" className="btn btn--ghost btn--sm" onClick={loadModels}>
            Оновити
          </button>
        </div>

        {loading ? (
          <div className="page-loading"><div className="spinner" /></div>
        ) : models.length === 0 ? (
          <p className="empty-state">Моделі не знайдено. Завантажте першу модель.</p>
        ) : (
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Назва</th>
                  <th>Розмір</th>
                  <th>Оновлено</th>
                  <th>Дії</th>
                </tr>
              </thead>
              <tbody>
                {models.map((model) => (
                  <tr key={model.name}>
                    <td><strong>{model.name}</strong></td>
                    <td>{formatBytes(model.size)}</td>
                    <td>{new Date(model.modified_at).toLocaleString('uk-UA')}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn--danger btn--sm"
                        onClick={() => handleDelete(model.name)}
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

export default ModelsPage;

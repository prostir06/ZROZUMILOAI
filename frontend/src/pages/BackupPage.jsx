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

function BackupPage() {
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const loadBackups = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.getBackups();
      setBackups(data.backups || []);
    } catch (err) {
      setError(err.message || 'Не вдалося завантажити список');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBackups();
  }, [loadBackups]);

  const handleCreate = async () => {
    setCreating(true);
    setError('');
    setSuccess('');
    try {
      const backup = await api.createBackup();
      setSuccess(`Резервну копію створено: ${backup.filename}`);
      loadBackups();
    } catch (err) {
      setError(err.message || 'Помилка створення backup');
    } finally {
      setCreating(false);
    }
  };

  const handleDownload = async (filename) => {
    try {
      await api.downloadBackup(filename);
    } catch (err) {
      setError(err.message || 'Помилка завантаження');
    }
  };

  const handleDelete = async (filename) => {
    if (!window.confirm(`Видалити резервну копію "${filename}"?`)) return;

    try {
      await api.deleteBackup(filename);
      loadBackups();
    } catch (err) {
      setError(err.message || 'Помилка видалення');
    }
  };

  return (
    <div className="page">
      <header className="page__header page__header--row">
        <div>
          <h2>Резервні копії</h2>
          <p>Створення та керування backup бази даних</p>
        </div>
        <button
          type="button"
          className="btn btn--primary"
          onClick={handleCreate}
          disabled={creating}
        >
          {creating ? 'Створення...' : 'Створити backup'}
        </button>
      </header>

      {error && <div className="alert alert--error" role="alert">{error}</div>}
      {success && <div className="alert alert--success" role="status">{success}</div>}

      <section className="section">
        <div className="section__header">
          <h3 className="section__title">Збережені копії</h3>
          <button type="button" className="btn btn--ghost btn--sm" onClick={loadBackups}>
            Оновити
          </button>
        </div>

        {loading ? (
          <div className="page-loading"><div className="spinner" /></div>
        ) : backups.length === 0 ? (
          <p className="empty-state">Резервних копій ще немає. Створіть першу backup.</p>
        ) : (
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Файл</th>
                  <th>Розмір</th>
                  <th>Тип БД</th>
                  <th>Дата</th>
                  <th>Дії</th>
                </tr>
              </thead>
              <tbody>
                {backups.map((item) => (
                  <tr key={item.filename}>
                    <td><strong>{item.filename}</strong></td>
                    <td>{formatBytes(item.size)}</td>
                    <td>{item.engine}</td>
                    <td>{new Date(item.created_at).toLocaleString('uk-UA')}</td>
                    <td className="table__actions">
                      <button
                        type="button"
                        className="btn btn--ghost btn--sm"
                        onClick={() => handleDownload(item.filename)}
                      >
                        Завантажити
                      </button>
                      <button
                        type="button"
                        className="btn btn--danger btn--sm"
                        onClick={() => handleDelete(item.filename)}
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

export default BackupPage;

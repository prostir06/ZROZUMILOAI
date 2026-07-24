/**
 * Секція документів RAG у формі редагування workspace.
 */
function documentStatusLabel(status) {
  if (status === 'ready') return 'Готовий';
  if (status === 'processing') return 'Обробка';
  if (status === 'failed') return 'Помилка';
  return status;
}

export default function DocumentsRagSection({
  documents,
  ragStats,
  uploadingDocument,
  onUpload,
  onRetry,
  onDelete,
  onReindexFailed,
}) {
  return (
    <div className="form workspaces-section workspaces-section--rag" style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--color-border-subtle)' }}>
      <h4 className="section__title">Документи (RAG)</h4>
      <p className="auth-card__subtitle" style={{ marginBottom: '1rem' }}>
        Завантажте TXT, MD або PDF. При чаті модель отримує релевантні фрагменти з цих документів.
        Потрібна embedding-модель Ollama: <code>nomic-embed-text</code>.
      </p>

      <div className="form__group">
        <label htmlFor="workspace_document_upload">Завантажити файл</label>
        <input
          id="workspace_document_upload"
          type="file"
          accept=".txt,.md,.markdown,.pdf"
          onChange={onUpload}
          disabled={uploadingDocument}
        />
        {uploadingDocument && (
          <p className="auth-card__subtitle">Індексація документа…</p>
        )}
      </div>

      {ragStats && (
        <p className="auth-card__subtitle">
          RAG: {ragStats.documents_ready}/{ragStats.documents_total} готово,
          {' '}
          {ragStats.chunks_total} фрагментів
          {ragStats.documents_failed > 0
            ? `, помилок: ${ragStats.documents_failed}`
            : ''}
          {ragStats.documents_failed > 0 && (
            <>
              {' '}
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                onClick={onReindexFailed}
              >
                Повторити всі failed
              </button>
            </>
          )}
        </p>
      )}

      {documents.length > 0 ? (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Файл</th>
                <th>Статус</th>
                <th>Фрагментів</th>
                <th>Завантажено</th>
                <th>Дії</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id}>
                  <td>
                    <strong>{doc.original_filename}</strong>
                    {doc.status === 'failed' && doc.error_message && (
                      <div className="auth-card__subtitle">{doc.error_message}</div>
                    )}
                  </td>
                  <td>{documentStatusLabel(doc.status)}</td>
                  <td>{doc.chunk_count || '—'}</td>
                  <td>{new Date(doc.created_at).toLocaleString('uk-UA')}</td>
                  <td className="table__actions">
                    {doc.status === 'failed' && (
                      <button
                        type="button"
                        className="btn btn--ghost btn--sm"
                        onClick={() => onRetry(doc.id)}
                      >
                        Повторити
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn btn--danger btn--sm"
                      onClick={() => onDelete(doc.id, doc.original_filename)}
                    >
                      Видалити
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="empty-state">Ще немає документів для RAG.</p>
      )}
    </div>
  );
}

/**
 * Секція налаштувань Meilisearch / Open edX у формі workspace.
 */
export default function MeilisearchSection({ form, setForm }) {
  return (
    <div className="form workspaces-section workspaces-section--meili" style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--color-border-subtle)' }}>
      <h4 className="section__title">Пошук Open edX (Meilisearch)</h4>
      <p className="auth-card__subtitle" style={{ marginBottom: '1rem' }}>
        Meilisearch Tutor: префікс <code>tutor_</code>, індекси
        <code>tutor_course_info</code> та <code>tutor_courseware_content</code>.
      </p>

      <div className="form__group">
        <label htmlFor="workspace_search_source">Джерело контексту для чату</label>
        <select
          id="workspace_search_source"
          value={form.search_source}
          onChange={(e) => setForm((prev) => ({ ...prev, search_source: e.target.value }))}
        >
          <option value="internal">Локальні документи (RAG)</option>
          <option value="meilisearch">Open edX Meilisearch</option>
          <option value="hybrid">RAG + Meilisearch</option>
        </select>
      </div>

      {form.search_source !== 'internal' && (
        <>
          <div className="form__group">
            <label htmlFor="workspace_meilisearch_url">Meilisearch URL</label>
            <input
              id="workspace_meilisearch_url"
              value={form.meilisearch_url}
              onChange={(e) => setForm((prev) => ({ ...prev, meilisearch_url: e.target.value }))}
              placeholder="meilisearch.local.openedx.io"
            />
          </div>

          <div className="form__group">
            <label htmlFor="workspace_meilisearch_api_key">API key</label>
            <input
              id="workspace_meilisearch_api_key"
              type="password"
              value={form.meilisearch_api_key}
              onChange={(e) => setForm((prev) => ({ ...prev, meilisearch_api_key: e.target.value }))}
              placeholder="Залиште порожнім, щоб не змінювати"
              autoComplete="new-password"
            />
          </div>

          <div className="form__row">
            <div className="form__group">
              <label htmlFor="workspace_meilisearch_prefix">Префікс індексів</label>
              <input
                id="workspace_meilisearch_prefix"
                value={form.meilisearch_index_prefix}
                onChange={(e) => setForm((prev) => ({ ...prev, meilisearch_index_prefix: e.target.value }))}
                placeholder="tutor_"
              />
            </div>
            <div className="form__group">
              <label htmlFor="workspace_meilisearch_indexes">Індекси (через кому)</label>
              <input
                id="workspace_meilisearch_indexes"
                value={form.meilisearch_indexes}
                onChange={(e) => setForm((prev) => ({ ...prev, meilisearch_indexes: e.target.value }))}
                placeholder="course_info, courseware_content"
              />
            </div>
          </div>

          <div className="form__group">
            <label htmlFor="workspace_meilisearch_course_id">Course ID (фільтр, опційно)</label>
            <input
              id="workspace_meilisearch_course_id"
              value={form.meilisearch_course_id}
              onChange={(e) => setForm((prev) => ({ ...prev, meilisearch_course_id: e.target.value }))}
              placeholder="course-v1:ORG+COURSE+RUN"
            />
          </div>
        </>
      )}
    </div>
  );
}

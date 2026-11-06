import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../api/client';
import KpiCards from '../../components/analytics/KpiCards';
import KnowledgeGapsTable from '../../components/analytics/KnowledgeGapsTable';

const RANGE_OPTIONS = [
  { id: 'today', label: 'Сьогодні' },
  { id: '7d', label: '7 днів' },
  { id: '30d', label: '30 днів' },
  { id: 'all', label: 'Весь час' },
];

/**
 * Workspace Analytics tab/section within workspace edit form.
 *
 * @param {Object} props
 * @param {number|string} props.workspaceId - ID of current editing workspace.
 * @param {Function} [props.onUploadMaterial] - Callback when "Додати матеріал" in KnowledgeGapsTable is triggered.
 * @param {Object|null} [props.initialAnalytics=null] - Optional initial data.
 */
export default function AnalyticsSection({
  workspaceId,
  onUploadMaterial,
  initialAnalytics = null,
}) {
  const [range, setRange] = useState('30d');
  const [analytics, setAnalytics] = useState(initialAnalytics);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState('');

  const loadAnalytics = useCallback(
    async (selectedRange) => {
      if (!workspaceId) return;
      setLoading(true);
      setError('');
      try {
        const data = await api.getWorkspaceAnalytics(workspaceId, { range: selectedRange });
        setAnalytics(data);
      } catch (err) {
        setError(err.message || 'Не вдалося завантажити аналітику');
      } finally {
        setLoading(false);
      }
    },
    [workspaceId],
  );

  useEffect(() => {
    if (workspaceId) {
      loadAnalytics(range);
    }
  }, [loadAnalytics, range, workspaceId]);

  const handleRangeChange = (newRange) => {
    if (newRange === range) return;
    setRange(newRange);
  };

  const handleExport = async () => {
    if (!workspaceId) return;
    setExporting(true);
    setError('');
    try {
      await api.exportWorkspaceAnalyticsCsv(workspaceId, { range });
    } catch (err) {
      setError(err.message || 'Не вдалося експортувати аналітику у CSV');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div
      className="form workspaces-section workspaces-section--analytics"
      id="workspace-analytics-section"
      style={{
        marginTop: '1.5rem',
        paddingTop: '1.5rem',
        borderTop: '1px solid var(--color-border-subtle)',
      }}
    >
      <div className="analytics-header">
        <div>
          <h4 className="section__title">Аналітика та прогалини знань</h4>
          <p className="auth-card__subtitle" style={{ marginBottom: '1rem' }}>
            Показники якості відповідей, задоволеність студентів (CSAT) та невідповіді для бази знань RAG.
          </p>
        </div>

        <div className="analytics-controls">
          <div className="analytics-range-selector" role="group" aria-label="Діапазон дат аналітики">
            {RANGE_OPTIONS.map((option) => (
              <button
                key={option.id}
                type="button"
                className={`btn btn--sm analytics-range-btn ${
                  range === option.id ? 'analytics-range-btn--active btn--primary' : 'btn--ghost'
                }`}
                onClick={() => handleRangeChange(option.id)}
                disabled={loading}
              >
                {option.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            className="btn btn--secondary btn--sm analytics-export-btn"
            onClick={handleExport}
            disabled={loading || exporting}
            title="Завантажити детальну аналітику у форматі CSV"
          >
            {exporting ? 'Експорт…' : '📥 Експорт CSV'}
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert--error" role="alert" style={{ marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {loading && !analytics ? (
        <div className="page-loading" style={{ minHeight: '120px' }}>
          <div className="spinner" />
        </div>
      ) : (
        <>
          <KpiCards analytics={analytics} isLoading={loading} />

          <div className="knowledge-gaps-section" style={{ marginTop: '1.75rem' }}>
            <div className="section__subheading" style={{ marginBottom: '0.75rem' }}>
              <h5 className="section__subtitle" style={{ fontSize: '1.05rem', margin: 0 }}>
                Черга прогалин знань (Knowledge Gaps)
              </h5>
              <p className="auth-card__subtitle" style={{ fontSize: '0.85rem', margin: '0.25rem 0 0 0' }}>
                Запити студентів із низькою впевненістю або негативною оцінкою. Додайте матеріали до бази RAG нижче.
              </p>
            </div>

            <KnowledgeGapsTable
              gaps={analytics?.knowledge_gaps}
              onUploadClick={onUploadMaterial}
            />
          </div>
        </>
      )}
    </div>
  );
}

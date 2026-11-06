import React from 'react';

/**
 * Formats relevance score safely into a percentage string (e.g. 85%).
 *
 * @param {number|null|undefined} score
 * @returns {string|null}
 */
function formatScore(score) {
  if (typeof score !== 'number' || Number.isNaN(score)) {
    return null;
  }
  const pct = score <= 1 ? Math.round(score * 100) : Math.round(score);
  return `${pct}%`;
}

/**
 * SourceCitations renders a list of retrieved document sources
 * with relevance badges and expandable citation snippets.
 *
 * @param {object} props
 * @param {Array<{ content?: string, score?: number, document_name?: string }>} [props.sources]
 */
export default function SourceCitations({ sources }) {
  if (!Array.isArray(sources) || sources.length === 0) {
    return null;
  }

  return (
    <div className="chat-citations" aria-label="Джерела">
      <div className="chat-citations__list">
        {sources.map((source, index) => {
          const docName = source?.document_name
            || source?.documentName
            || source?.source
            || 'Джерело';
          const scoreText = formatScore(source?.score);
          const content = source?.content;

          return (
            <details
              key={`${docName}-${index}`}
              className="chat-citation"
            >
              <summary className="chat-citation__summary">
                <span className="chat-citation__badge">
                  <span className="chat-citation__name">{docName}</span>
                  {scoreText && (
                    <span className="chat-citation__score">{scoreText}</span>
                  )}
                </span>
              </summary>
              {content && (
                <div className="chat-citation__content">
                  <p>{content}</p>
                </div>
              )}
            </details>
          );
        })}
      </div>
    </div>
  );
}

import React, { useCallback } from 'react';
import MarkdownMessage from './MarkdownMessage';
import SourceCitations from './SourceCitations';

/**
 * ChatMessage renders a single chat message (user or assistant)
 * including role indicators, avatars, markdown formatting,
 * document source citations, and feedback / human handoff controls.
 *
 * @param {object} props
 * @param {object} props.message - Message entity
 * @param {string} props.message.role - 'user' | 'assistant'
 * @param {string} props.message.content - Message markdown content
 * @param {Array} [props.message.sources] - Retrieval sources
 * @param {string|number} [props.message.logId] - Feedback log ID
 * @param {string} [props.message.feedback] - Current feedback ('up'|'down')
 * @param {boolean} [props.message.needsHandoff] - Low confidence flag
 * @param {(message: object, feedback: 'up'|'down') => void} [props.onFeedback]
 * @param {(message: object) => void} [props.onRequestHandoff]
 * @param {boolean} [props.isStreaming=false]
 */
export default function ChatMessage({
  message,
  onFeedback,
  onRequestHandoff,
  isStreaming = false,
}) {
  const handleFeedbackUp = useCallback(() => {
    try {
      onFeedback?.(message, 'up');
    } catch (err) {
      console.error('Error in onFeedback handler:', err);
    }
  }, [message, onFeedback]);

  const handleFeedbackDown = useCallback(() => {
    try {
      onFeedback?.(message, 'down');
    } catch (err) {
      console.error('Error in onFeedback handler:', err);
    }
  }, [message, onFeedback]);

  const handleHandoff = useCallback(() => {
    try {
      onRequestHandoff?.(message);
    } catch (err) {
      console.error('Error in onRequestHandoff handler:', err);
    }
  }, [message, onRequestHandoff]);

  if (!message) {
    return null;
  }

  const role = message.role || 'user';
  const isAssistant = role === 'assistant';
  const content = message.content ?? '';
  const isPendingAssistant = isAssistant && isStreaming && !content.trim();

  if (isAssistant) {
    return (
      <div className="chat-message-row chat-message-row--assistant">
        <img
          src="/zrozumilo-assistant.png"
          alt="Помічник"
          className="chat-message__avatar"
          width={28}
          height={28}
        />
        {isPendingAssistant ? (
          <div className="chat-typing" aria-label="Помічник друкує">
            <span />
            <span />
            <span />
          </div>
        ) : (
          <div className="chat-message chat-message--assistant">
            <div className="chat-message__role">Помічник</div>
            <div className="chat-message__content">
              <MarkdownMessage content={content} isStreaming={isStreaming} />
            </div>

            {Array.isArray(message.sources) && message.sources.length > 0 && (
              <SourceCitations sources={message.sources} />
            )}

            {(message.needsHandoff || message.logId) && !isStreaming && (
              <div className="chat-feedback">
                {message.needsHandoff && (
                  <span className="chat-feedback__hint">
                    Низька впевненість — можна звернутися до підтримки
                  </span>
                )}
                {message.logId && (
                  <>
                    <button
                      type="button"
                      className={`btn btn--ghost btn--sm${message.feedback === 'up' ? ' is-active' : ''}`}
                      onClick={handleFeedbackUp}
                      aria-label="Корисна відповідь"
                      aria-pressed={message.feedback === 'up'}
                    >
                      👍
                    </button>
                    <button
                      type="button"
                      className={`btn btn--ghost btn--sm${message.feedback === 'down' ? ' is-active' : ''}`}
                      onClick={handleFeedbackDown}
                      aria-label="Некорисна відповідь"
                      aria-pressed={message.feedback === 'down'}
                    >
                      👎
                    </button>
                    {!message.needsHandoff && (
                      <button
                        type="button"
                        className="btn btn--ghost btn--sm"
                        onClick={handleHandoff}
                        aria-label="Запросити допомогу людини"
                      >
                        До людини
                      </button>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="chat-message-row chat-message-row--user">
      <div className="chat-message chat-message--user">
        <div className="chat-message__role">Ви</div>
        <div className="chat-message__content">
          <MarkdownMessage content={content} isStreaming={false} />
        </div>
      </div>
      <div
        className="chat-message__avatar chat-message__avatar--user"
        aria-label="Користувач"
      >
        U
      </div>
    </div>
  );
}

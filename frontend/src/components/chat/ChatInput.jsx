import React, { useCallback, useEffect, useRef } from 'react';

/**
 * ChatInput provides a multiline auto-resizing textarea with keyboard
 * shortcuts (Enter to send, Shift+Enter for newline) and submit/stop controls.
 *
 * @param {object} props
 * @param {string} props.input - Current input text
 * @param {(text: string) => void} props.setInput - State setter for input
 * @param {(e?: React.FormEvent) => void} props.onSubmit - Submission callback
 * @param {(e?: React.MouseEvent) => void} [props.onStop] - Stream cancellation callback
 * @param {boolean} [props.streaming=false] - Whether response is currently streaming
 * @param {boolean} [props.loading=false] - Whether request is pending
 * @param {boolean} [props.disabled=false] - Overall disabled state
 */
export default function ChatInput({
  input = '',
  setInput,
  onSubmit,
  onStop,
  streaming = false,
  loading = false,
  disabled = false,
}) {
  const textareaRef = useRef(null);

  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const nextHeight = Math.min(el.scrollHeight, 200);
    el.style.height = `${Math.max(nextHeight, 44)}px`;
  }, []);

  useEffect(() => {
    adjustHeight();
  }, [input, adjustHeight]);

  const handleChange = useCallback((e) => {
    try {
      setInput?.(e.target.value);
    } catch (err) {
      console.error('Error in setInput handler:', err);
    }
  }, [setInput]);

  const handleSubmit = useCallback((e) => {
    e?.preventDefault?.();
    if (!input?.trim() || disabled || loading || streaming) {
      return;
    }
    try {
      onSubmit?.(e);
    } catch (err) {
      console.error('Error submitting chat input:', err);
    }
  }, [input, disabled, loading, streaming, onSubmit]);

  const handleStop = useCallback((e) => {
    e?.preventDefault?.();
    try {
      onStop?.(e);
    } catch (err) {
      console.error('Error in onStop handler:', err);
    }
  }, [onStop]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }, [handleSubmit]);

  const isSubmitDisabled = !input?.trim() || disabled || loading || streaming;

  return (
    <form className="chat-input" onSubmit={handleSubmit}>
      <textarea
        ref={textareaRef}
        value={input}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder="Введіть повідомлення..."
        aria-label="Текст повідомлення"
        rows={2}
        maxLength={16000}
        disabled={disabled || loading}
      />

      {streaming ? (
        <button
          type="button"
          className="btn btn--ghost chat-input__btn chat-input__btn--stop"
          onClick={handleStop}
          aria-label="Зупинити генерацію відповіді"
        >
          Зупинити
        </button>
      ) : (
        <button
          type="submit"
          className="btn btn--primary chat-input__btn"
          disabled={isSubmitDisabled}
          aria-label="Надіслати"
        >
          <span>Надіслати</span>
          <svg
            viewBox="0 0 24 24"
            aria-hidden="true"
            className="chat-input__send-icon"
            width={16}
            height={16}
            fill="currentColor"
          >
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
          </svg>
        </button>
      )}
    </form>
  );
}

import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Custom hook to manage chat streaming lifecycle, AbortController cancellation,
 * token buffering with requestAnimationFrame, and SSE metadata handling.
 *
 * @param {object} [initialCallbacks={}]
 * @param {(textChunk: string) => void} [initialCallbacks.onChunk]
 * @param {(sources: Array) => void} [initialCallbacks.onSources]
 * @param {(meta: object) => void} [initialCallbacks.onMeta]
 * @param {(error: Error) => void} [initialCallbacks.onError]
 * @param {() => void} [initialCallbacks.onDone]
 * @returns {{
 *   streaming: boolean,
 *   loading: boolean,
 *   startStream: (options: object|Function) => Promise<void>,
 *   abortStream: () => void
 * }}
 */
export function useChatStream(initialCallbacks = {}) {
  const [streaming, setStreaming] = useState(false);
  const [loading, setLoading] = useState(false);

  const streamAbortRef = useRef(null);
  const streamRafRef = useRef(null);
  const streamPendingRef = useRef('');
  const isMountedRef = useRef(true);
  const callbacksRef = useRef(initialCallbacks);
  const currentOnChunkRef = useRef(initialCallbacks?.onChunk);

  callbacksRef.current = initialCallbacks;

  const abortStream = useCallback(() => {
    try {
      streamAbortRef.current?.abort();
    } catch (_err) {
      // Guard against non-standard polyfill issues
    }
    streamAbortRef.current = null;

    if (streamRafRef.current) {
      if (typeof cancelAnimationFrame === 'function') {
        cancelAnimationFrame(streamRafRef.current);
      }
      streamRafRef.current = null;
    }

    const remainingText = streamPendingRef.current;
    streamPendingRef.current = '';
    if (remainingText && currentOnChunkRef.current) {
      try {
        currentOnChunkRef.current(remainingText);
      } catch (cbErr) {
        console.error('Error in onChunk callback during flush:', cbErr);
      }
    }

    if (isMountedRef.current) {
      setLoading(false);
      setStreaming(false);
    }
  }, []);

  const startStream = useCallback(async (options = {}) => {
    const opts = typeof options === 'function' ? { apiCall: options } : (options || {});
    const apiCall = opts.apiCall;
    const onChunk = opts.onChunk || callbacksRef.current?.onChunk;
    const onSources = opts.onSources || callbacksRef.current?.onSources;
    const onMeta = opts.onMeta || callbacksRef.current?.onMeta;
    const onError = opts.onError || callbacksRef.current?.onError;
    const onDone = opts.onDone || callbacksRef.current?.onDone;

    currentOnChunkRef.current = onChunk;

    abortStream();

    const controller = new AbortController();
    streamAbortRef.current = controller;
    const signal = controller.signal;

    if (isMountedRef.current) {
      setLoading(true);
      setStreaming(true);
    }

    streamPendingRef.current = '';

    // rAF throttle buffers incoming tokens to prevent UI thread lock during fast token streams
    const scheduleRaf = () => {
      if (streamRafRef.current) {
        return;
      }
      if (typeof requestAnimationFrame !== 'function') {
        const pendingText = streamPendingRef.current;
        streamPendingRef.current = '';
        if (pendingText && onChunk) {
          onChunk(pendingText);
        }
        return;
      }
      streamRafRef.current = requestAnimationFrame(() => {
        streamRafRef.current = null;
        const pendingText = streamPendingRef.current;
        streamPendingRef.current = '';
        if (pendingText && onChunk) {
          onChunk(pendingText);
        }
      });
    };

    const handleIncomingChunk = (chunk) => {
      if (!chunk) {
        return;
      }

      if (chunk.error) {
        const err = chunk.error instanceof Error
          ? chunk.error
          : new Error(String(chunk.error));
        console.error('Chat stream received error chunk:', err);
        try {
          onError?.(err);
        } catch (cbErr) {
          console.error('Error in onError callback:', cbErr);
        }
        return;
      }

      if (Array.isArray(chunk.sources) && onSources) {
        try {
          onSources(chunk.sources);
        } catch (cbErr) {
          console.error('Error in onSources callback:', cbErr);
        }
      }

      if (
        (chunk.log_id != null || typeof chunk.needs_handoff === 'boolean' || chunk.meta)
        && onMeta
      ) {
        try {
          onMeta(chunk.meta || chunk);
        } catch (cbErr) {
          console.error('Error in onMeta callback:', cbErr);
        }
      }

      let text = '';
      if (typeof chunk === 'string') {
        text = chunk;
      } else if (chunk.message?.content) {
        text = chunk.message.content;
      } else if (chunk.content) {
        text = chunk.content;
      } else if (chunk.text) {
        text = chunk.text;
      }

      if (text) {
        streamPendingRef.current += text;
        scheduleRaf();
      }
    };

    signal.signal = signal;
    signal.onChunk = handleIncomingChunk;
    signal.handleChunk = handleIncomingChunk;

    try {
      if (typeof apiCall === 'function') {
        await apiCall(signal, handleIncomingChunk);
      }
    } catch (err) {
      if (err?.name === 'AbortError') {
        return;
      }
      console.error('Chat stream error:', err);
      try {
        onError?.(err);
      } catch (cbErr) {
        console.error('Error in onError callback:', cbErr);
      }
    } finally {
      if (streamRafRef.current) {
        if (typeof cancelAnimationFrame === 'function') {
          cancelAnimationFrame(streamRafRef.current);
        }
        streamRafRef.current = null;
      }

      const remainingText = streamPendingRef.current;
      streamPendingRef.current = '';
      if (remainingText && onChunk) {
        try {
          onChunk(remainingText);
        } catch (cbErr) {
          console.error('Error in onChunk callback during flush:', cbErr);
        }
      }

      if (isMountedRef.current) {
        setLoading(false);
        setStreaming(false);
      }
      streamAbortRef.current = null;

      try {
        onDone?.();
      } catch (cbErr) {
        console.error('Error in onDone callback:', cbErr);
      }
    }
  }, [abortStream]);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      try {
        streamAbortRef.current?.abort();
      } catch (_err) {
        /* ignore */
      }
      if (streamRafRef.current) {
        if (typeof cancelAnimationFrame === 'function') {
          cancelAnimationFrame(streamRafRef.current);
        }
        streamRafRef.current = null;
      }
    };
  }, []);

  return {
    streaming,
    loading,
    startStream,
    abortStream,
  };
}

export default useChatStream;

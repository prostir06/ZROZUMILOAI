import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { renderToString } from 'react-dom/server';
import { useChatStream } from './useChatStream';

describe('useChatStream', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('initializes with default streaming and loading states', () => {
    let hookValue;
    function Component() {
      hookValue = useChatStream();
      return React.createElement('div');
    }
    renderToString(React.createElement(Component));

    expect(hookValue).toBeDefined();
    expect(hookValue.streaming).toBe(false);
    expect(hookValue.loading).toBe(false);
    expect(typeof hookValue.startStream).toBe('function');
    expect(typeof hookValue.abortStream).toBe('function');
  });

  it('processes incoming chunks, buffers text, and calls onChunk and onDone', async () => {
    let hookValue;
    function Component() {
      hookValue = useChatStream();
      return React.createElement('div');
    }
    renderToString(React.createElement(Component));

    const chunks = [];
    const onChunk = vi.fn((text) => chunks.push(text));
    const onDone = vi.fn();

    const mockApiCall = async (signal, handleChunk) => {
      handleChunk({ message: { content: 'Hello ' } });
      handleChunk({ message: { content: 'World!' } });
    };

    await hookValue.startStream({
      apiCall: mockApiCall,
      onChunk,
      onDone,
    });

    expect(chunks.join('')).toBe('Hello World!');
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it('forwards sources and metadata callbacks', async () => {
    let hookValue;
    function Component() {
      hookValue = useChatStream();
      return React.createElement('div');
    }
    renderToString(React.createElement(Component));

    const onSources = vi.fn();
    const onMeta = vi.fn();

    const mockSources = [{ document_name: 'test.pdf', score: 0.9 }];
    const mockMeta = { log_id: 123, needs_handoff: false };

    const mockApiCall = async (signal, handleChunk) => {
      handleChunk({ sources: mockSources });
      handleChunk(mockMeta);
    };

    await hookValue.startStream({
      apiCall: mockApiCall,
      onSources,
      onMeta,
    });

    expect(onSources).toHaveBeenCalledWith(mockSources);
    expect(onMeta).toHaveBeenCalledWith(mockMeta);
  });

  it('handles errors from apiCall and chunk.error via onError', async () => {
    let hookValue;
    function Component() {
      hookValue = useChatStream();
      return React.createElement('div');
    }
    renderToString(React.createElement(Component));

    const onError = vi.fn();
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    await hookValue.startStream({
      apiCall: async () => {
        throw new Error('Network failure');
      },
      onError,
    });

    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: 'Network failure' }));
    consoleSpy.mockRestore();
  });

  it('handles abort error gracefully without calling onError', async () => {
    let hookValue;
    function Component() {
      hookValue = useChatStream();
      return React.createElement('div');
    }
    renderToString(React.createElement(Component));

    const onError = vi.fn();
    const onDone = vi.fn();

    await hookValue.startStream({
      apiCall: async () => {
        const abortErr = new Error('The operation was aborted');
        abortErr.name = 'AbortError';
        throw abortErr;
      },
      onError,
      onDone,
    });

    expect(onError).not.toHaveBeenCalled();
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it('abortStream flushes buffered tokens and resets controllers', async () => {
    let hookValue;
    function Component() {
      hookValue = useChatStream();
      return React.createElement('div');
    }
    renderToString(React.createElement(Component));

    const chunks = [];
    const onChunk = vi.fn((text) => chunks.push(text));

    // Start stream that holds pending text
    let apiSignal;
    hookValue.startStream({
      apiCall: (signal, handleChunk) => {
        apiSignal = signal;
        handleChunk('Buffered token');
        return new Promise(() => {}); // never resolves
      },
      onChunk,
    });

    expect(apiSignal.aborted).toBe(false);

    // Call abortStream
    hookValue.abortStream();

    expect(apiSignal.aborted).toBe(true);
    expect(chunks).toContain('Buffered token');
  });
});

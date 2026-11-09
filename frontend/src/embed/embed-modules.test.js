import { describe, expect, it, vi, beforeEach } from 'vitest';
import { createEmbedState, getGreetingText, getFaqQuestions } from './embed-state.js';
import { apiRequest, fetchWorkspaceConfig, sendChatMessageStream, sendFeedback } from './embed-api.js';
import {
  renderAssistantIcon,
  wrapAssistantMessage,
  renderTypingIndicator,
  renderFaqCloud,
  renderMessages,
  renderEmbedLayout,
  appendAssistantText,
} from './embed-dom.js';
import { EMBED_GREETING, EMBED_FAQ_QUESTIONS } from './utils.js';

describe('embed-state', () => {
  it('initializes with default state', () => {
    const store = createEmbedState();
    const state = store.getState();
    expect(state.config).toBeNull();
    expect(state.workspace).toBeNull();
    expect(state.model).toBe('');
    expect(state.initError).toBe('');
    expect(state.messages).toEqual([]);
    expect(state.isStreaming).toBe(false);
  });

  it('updates state and notifies subscribers', () => {
    const store = createEmbedState();
    const listener = vi.fn();
    const unsubscribe = store.subscribe(listener);

    store.setState({ model: 'llama3:latest' });
    expect(store.getState().model).toBe('llama3:latest');
    expect(listener).toHaveBeenCalledWith(expect.objectContaining({ model: 'llama3:latest' }));

    unsubscribe();
    store.setState({ model: 'mistral' });
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it('computes greeting text correctly', () => {
    const store = createEmbedState();
    expect(store.getGreetingText()).toBe(EMBED_GREETING);

    store.setState({ config: { greeting: 'Custom config greeting' } });
    expect(store.getGreetingText()).toBe('Custom config greeting');

    store.setState({ workspace: { greeting: 'Custom workspace greeting' } });
    expect(store.getGreetingText()).toBe('Custom workspace greeting');

    // Standalone helper
    expect(getGreetingText({ workspace: { greeting: 'Hello helper' } })).toBe('Hello helper');
    expect(getGreetingText({})).toBe(EMBED_GREETING);
  });

  it('computes FAQ questions correctly', () => {
    const store = createEmbedState();
    expect(store.getFaqQuestions()).toEqual(EMBED_FAQ_QUESTIONS);

    store.setState({ config: { faqQuestions: ['Q1', 'Q2'] } });
    expect(store.getFaqQuestions()).toEqual(['Q1', 'Q2']);

    store.setState({
      workspace: {
        faq_questions: [' WQ1 ', 'WQ2', '', 'WQ3', 'WQ4', 'WQ5', 'WQ6', 'WQ7', 'WQ8', 'WQ9'],
      },
    });
    // Trims, filters out empty, limits to 8
    expect(store.getFaqQuestions()).toEqual(['WQ1', 'WQ2', 'WQ3', 'WQ4', 'WQ5', 'WQ6', 'WQ7', 'WQ8']);

    // Standalone helper
    expect(getFaqQuestions({})).toEqual(EMBED_FAQ_QUESTIONS);
  });

  it('appends messages and updates assistant messages', () => {
    const store = createEmbedState();
    store.addMessage({ role: 'user', content: 'Привіт' });
    expect(store.getState().messages).toHaveLength(1);
    expect(store.getState().messages[0]).toEqual({ role: 'user', content: 'Привіт' });

    store.addMessage({ role: 'assistant', content: 'Вітаю' });
    expect(store.getState().messages).toHaveLength(2);

    store.updateLastAssistantMessage({ content: 'Вітаю!', logId: 101 });
    expect(store.getState().messages[1]).toEqual({
      role: 'assistant',
      content: 'Вітаю!',
      logId: 101,
    });
  });

  it('updates feedback on matching message', () => {
    const store = createEmbedState({
      messages: [
        { role: 'user', content: 'Hi' },
        { role: 'assistant', content: 'Answer', logId: 42 },
      ],
    });

    store.updateFeedback(42, { feedback: 'up', needs_handoff: true });
    const assistantMsg = store.getState().messages[1];
    expect(assistantMsg.feedback).toBe('up');
    expect(assistantMsg.needsHandoff).toBe(true);
  });

  it('resets state', () => {
    const store = createEmbedState({ model: 'test', messages: [{ role: 'user', content: 'msg' }] });
    store.reset();
    expect(store.getState().model).toBe('');
    expect(store.getState().messages).toEqual([]);
  });
});

describe('embed-api', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('apiRequest attaches authorization header and sends json request', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'ok' }),
    });
    vi.stubGlobal('fetch', mockFetch);

    const config = {
      apiUrl: 'https://api.example.com',
      widgetToken: 'valid-widget-token',
    };

    const res = await apiRequest(config, '/widget/config/');
    expect(mockFetch).toHaveBeenCalledWith(
      'https://api.example.com/widget/config/',
      expect.objectContaining({
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          Authorization: 'Widget-Token valid-widget-token',
        }),
      }),
    );
    expect(res.ok).toBe(true);
  });

  it('fetchWorkspaceConfig handles invalid widget token', async () => {
    const config = {
      apiUrl: 'https://api.example.com',
      widgetToken: 'невалідний-токен-з-кирилицею',
    };

    const result = await fetchWorkspaceConfig(config);
    expect(result.workspace).toBeNull();
    expect(result.model).toBe('');
    expect(result.initError).toContain('Некоректний токен');
  });

  it('fetchWorkspaceConfig loads config via widgetToken', async () => {
    const mockData = {
      workspace: { id: 1, name: 'Main WS', model_names: ['llama3'] },
      model: 'llama3',
      greeting: 'Привіт від workspace',
      faq_questions: ['Q1', 'Q2'],
    };

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData,
    });
    vi.stubGlobal('fetch', mockFetch);

    const config = {
      apiUrl: 'https://api.example.com',
      widgetToken: 'token123',
    };

    const result = await fetchWorkspaceConfig(config);
    expect(result.workspace.name).toBe('Main WS');
    expect(result.workspace.greeting).toBe('Привіт від workspace');
    expect(result.workspace.faq_questions).toEqual(['Q1', 'Q2']);
    expect(result.model).toBe('llama3');
    expect(result.initError).toBe('');
  });

  it('fetchWorkspaceConfig handles widget config fetch error', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Invalid token' }),
    });
    vi.stubGlobal('fetch', mockFetch);

    const config = {
      apiUrl: 'https://api.example.com',
      widgetToken: 'invalid',
    };

    const result = await fetchWorkspaceConfig(config);
    expect(result.workspace).toBeNull();
    expect(result.initError).toBe('Invalid token');
  });

  it('fetchWorkspaceConfig loads workspace via apiKey', async () => {
    const workspaces = [
      { id: 1, name: 'Other WS' },
      { id: 2, name: 'Target WS', model_names: ['gpt-model'] },
    ];

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => workspaces,
    });
    vi.stubGlobal('fetch', mockFetch);

    const config = {
      apiUrl: 'https://api.example.com',
      apiKey: 'api-key-123',
      workspaceName: 'Target WS',
    };

    const result = await fetchWorkspaceConfig(config);
    expect(result.workspace.id).toBe(2);
    expect(result.model).toBe('gpt-model');
    expect(result.initError).toBe('');
  });

  it('sendChatMessageStream streams SSE chunks to onChunk', async () => {
    const encoder = new TextEncoder();
    const chunks = [
      encoder.encode('data: {"message":{"content":"Hello"}}\n\n'),
      encoder.encode('data: {"message":{"content":" world"}}\n\n'),
      encoder.encode('data: {"log_id":55,"needs_handoff":false}\n\n'),
    ];

    let chunkIndex = 0;
    const mockReader = {
      read: vi.fn().mockImplementation(async () => {
        if (chunkIndex < chunks.length) {
          const value = chunks[chunkIndex++];
          return { done: false, value };
        }
        return { done: true, value: undefined };
      }),
    };

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader: () => mockReader,
      },
    });
    vi.stubGlobal('fetch', mockFetch);

    const config = { apiUrl: 'https://api.example.com', widgetToken: 'token' };
    const received = [];

    await sendChatMessageStream({
      config,
      workspace: { id: 1 },
      model: 'test',
      messages: [{ role: 'user', content: 'hi' }],
      onChunk: (chunk) => received.push(chunk),
    });

    expect(received).toHaveLength(3);
    expect(received[0].message.content).toBe('Hello');
    expect(received[1].message.content).toBe(' world');
    expect(received[2].log_id).toBe(55);
  });

  it('sendFeedback sends post request with payload', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'ok' }),
    });
    vi.stubGlobal('fetch', mockFetch);

    const config = { apiUrl: 'https://api.example.com', widgetToken: 'tok' };
    await sendFeedback({ config, logId: 12, payload: { feedback: 'up' } });

    expect(mockFetch).toHaveBeenCalledWith(
      'https://api.example.com/widget/logs/12/feedback/',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ feedback: 'up' }),
      }),
    );
  });
});

describe('embed-dom', () => {
  it('renders assistant icon and wraps assistant message', () => {
    const icon = renderAssistantIcon();
    expect(icon).toContain('<img');
    expect(icon).toContain('class="embed__assistant-icon"');

    const wrapped = wrapAssistantMessage('<span>Текст</span>');
    expect(wrapped).toContain('class="embed__assistant"');
    expect(wrapped).toContain('<span>Текст</span>');
  });

  it('renders typing indicator', () => {
    const typing = renderTypingIndicator();
    expect(typing).toContain('class="embed__typing"');
    expect(typing).toContain('<span></span><span></span><span></span>');
  });

  it('appendAssistantText returns false when typing indicator is present or container missing', () => {
    expect(appendAssistantText(null, 'test')).toBe(false);

    const mockLastBubble = { insertAdjacentText: vi.fn() };
    const containerWithTyping = {
      querySelector: (sel) => (sel === '.embed__typing' ? {} : null),
      querySelectorAll: (sel) => (sel === '.embed__message--assistant' ? [mockLastBubble] : []),
    };
    expect(appendAssistantText(containerWithTyping, ' world')).toBe(false);
    expect(mockLastBubble.insertAdjacentText).not.toHaveBeenCalled();

    const normalContainer = {
      querySelector: () => null,
      querySelectorAll: (sel) => (sel === '.embed__message--assistant' ? [mockLastBubble] : []),
      scrollHeight: 100,
      scrollTop: 100,
      clientHeight: 50,
    };
    expect(appendAssistantText(normalContainer, ' world')).toBe(true);
    expect(mockLastBubble.insertAdjacentText).toHaveBeenCalledWith('beforeend', ' world');
  });

  it('renders FAQ cloud when model is available', () => {
    expect(renderFaqCloud({ model: '' })).toBe('');

    const html = renderFaqCloud({
      model: 'model-1',
      isStreaming: false,
      questions: ['Питання 1', 'Питання 2'],
    });
    expect(html).toContain('class="embed__faq"');
    expect(html).toContain('Питання 1');
    expect(html).toContain('Питання 2');
    expect(html).not.toContain('disabled');

    const streamingHtml = renderFaqCloud({
      model: 'model-1',
      isStreaming: true,
      questions: ['Питання 1'],
    });
    expect(streamingHtml).toContain('disabled');
  });

  it('renders messages and welcome state', () => {
    const welcomeHtml = renderMessages({
      messages: [],
      isStreaming: false,
      typedGreeting: 'Привіт!',
    });
    expect(welcomeHtml).toContain('embed__welcome');
    expect(welcomeHtml).toContain('id="embed-greeting"');
    expect(welcomeHtml).toContain('Привіт!');

    const chatHtml = renderMessages({
      messages: [
        { role: 'user', content: 'Чи працює чат?' },
        { role: 'assistant', content: 'Так, **працює**!', logId: 77, needsHandoff: true },
      ],
      isStreaming: false,
    });
    expect(chatHtml).toContain('embed__message--user');
    expect(chatHtml).toContain('Чи працює чат?');
    expect(chatHtml).toContain('embed__message--assistant');
    expect(chatHtml).toContain('<strong>працює</strong>');
    expect(chatHtml).toContain('data-log-id="77"');
    expect(chatHtml).toContain('embed__handoff');
  });

  it('renders layout skeleton', () => {
    const layout = renderEmbedLayout({
      config: { title: 'Підтримка клієнтів' },
      workspace: { name: 'Головний Workspace' },
      model: 'llama3',
      messages: [],
      typedGreeting: 'Вітаю',
    });
    expect(layout).toContain('Підтримка клієнтів');
    expect(layout).toContain('Головний Workspace');
    expect(layout).toContain('embed__status');
    expect(layout).toContain('embed__messages');
    expect(layout).toContain('embed__footer');
  });
});

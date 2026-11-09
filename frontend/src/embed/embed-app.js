/**
 * Embed-чат у iframe: отримує конфіг від widget.js, керує станом та взаємодією.
 */
import { formatChatError } from '../utils/chatError.js';
import './embed.css';
import { createEmbedState } from './embed-state.js';
import { fetchWorkspaceConfig, sendChatMessageStream, sendFeedback } from './embed-api.js';
import {
  appendAssistantText,
  applyThemeColor,
  attachFaqListeners,
  attachFeedbackListeners,
  isNearBottom,
  renderEmbedLayout,
  renderMessages,
  scrollToBottom,
} from './embed-dom.js';

const root = document.getElementById('embed-root');
const CONFIG_TIMEOUT_MS = 15000;

const store = createEmbedState();
let typewriterTimer = null;

/** Зупинити анімацію «друкування» привітання. */
function stopGreetingTypewriter() {
  if (typewriterTimer) {
    clearInterval(typewriterTimer);
    typewriterTimer = null;
  }
}

/** Оновити текст привітання в DOM без повного render. */
function updateGreetingElement() {
  const greetingEl = root?.querySelector('#embed-greeting');
  const cursorEl = root?.querySelector('#embed-greeting-cursor');
  const typedGreeting = store.getState().typedGreeting;
  const fullGreeting = store.getGreetingText();

  if (greetingEl) {
    greetingEl.textContent = typedGreeting;
  }
  if (cursorEl) {
    cursorEl.hidden = typedGreeting.length >= fullGreeting.length;
  }
}

/** Ефект друкування привітання при відкритті форми. */
function startGreetingTypewriter() {
  const greeting = store.getGreetingText();
  const state = store.getState();
  if (
    typewriterTimer
    || state.messages.length > 0
    || !state.model
    || state.typedGreeting.length >= greeting.length
  ) {
    return;
  }

  store.setState({ typedGreeting: '' });
  let index = 0;
  typewriterTimer = setInterval(() => {
    if (index >= greeting.length) {
      stopGreetingTypewriter();
      updateGreetingElement();
      return;
    }
    store.setState((prev) => ({ typedGreeting: prev.typedGreeting + greeting[index] }));
    index += 1;
    updateGreetingElement();
  }, 28);
}

/** Оновлення лише блоку повідомлень (без повного render). */
function updateMessages() {
  const container = root?.querySelector('#embed-messages');
  if (!container) {
    return;
  }

  const wasNearBottom = isNearBottom(container);
  const state = store.getState();

  container.innerHTML = renderMessages({
    messages: state.messages,
    isStreaming: state.isStreaming,
    typedGreeting: state.typedGreeting,
  });

  if (wasNearBottom) {
    scrollToBottom(container);
  }

  attachFeedbackListeners(container, handleFeedback);
}

/** Надіслати feedback з embed через Widget-Token. */
async function handleFeedback(logId, payload) {
  try {
    await sendFeedback({
      config: store.getState().config,
      logId,
      payload,
    });
    store.updateFeedback(logId, payload);
    updateMessages();
  } catch (err) {
    console.error('[ZrozumiloAI Embed] feedback error:', err);
  }
}

/** Повний перерендер UI embed-чату. */
function render() {
  if (!root) {
    return;
  }

  const state = store.getState();
  root.innerHTML = renderEmbedLayout({
    ...state,
    questions: store.getFaqQuestions(),
  });

  if (!state.config) {
    return;
  }

  root.querySelector('.embed__close')?.addEventListener('click', () => {
    const targetOrigin = store.getState().trustedOrigin || '*';
    window.parent.postMessage({ type: 'zrozumiloai-close' }, targetOrigin);
  });

  const form = root.querySelector('#embed-form');
  const input = root.querySelector('#embed-input');

  form?.addEventListener('submit', (event) => {
    event.preventDefault();
    handleSend(input?.value || '');
  });

  input?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      form?.requestSubmit();
    }
  });

  attachFaqListeners(root, (question) => handleSend(question));
  attachFeedbackListeners(root.querySelector('#embed-messages'), handleFeedback);

  if (state.messages.length === 0 && state.model) {
    updateGreetingElement();
    if (state.typedGreeting.length < store.getGreetingText().length && !typewriterTimer) {
      startGreetingTypewriter();
    }
  }

  scrollToBottom(root.querySelector('#embed-messages'));
}

/** Обробка надсилання повідомлення користувачем. */
async function handleSend(text) {
  const content = text.trim();
  const state = store.getState();
  if (!content || !state.model || !state.workspace || state.isStreaming) {
    return;
  }

  stopGreetingTypewriter();
  store.setState({ typedGreeting: store.getGreetingText() });

  store.addMessage({ role: 'user', content });
  store.setState({ isStreaming: true });
  render();

  const chatMessages = store.getState().messages.map((msg) => ({ role: msg.role, content: msg.content }));
  store.addMessage({ role: 'assistant', content: '' });
  updateMessages();

  const container = root?.querySelector('#embed-messages');

  try {
    await sendChatMessageStream({
      config: store.getState().config,
      workspace: store.getState().workspace,
      model: store.getState().model,
      messages: chatMessages,
      onChunk: (chunk) => {
        if (chunk.message?.content) {
          store.updateLastAssistantMessage((msg) => ({
            content: msg.content + chunk.message.content,
          }));
          const appended = appendAssistantText(container, chunk.message.content);
          if (!appended) {
            updateMessages();
          }
        }
        if (chunk.error) {
          store.updateLastAssistantMessage({ content: `Помилка: ${chunk.error}` });
          updateMessages();
        }
        if (chunk.log_id != null || typeof chunk.needs_handoff === 'boolean') {
          store.updateLastAssistantMessage({
            ...(chunk.log_id != null ? { logId: chunk.log_id } : {}),
            ...(typeof chunk.needs_handoff === 'boolean'
              ? { needsHandoff: chunk.needs_handoff }
              : {}),
          });
          updateMessages();
        }
      },
    });
  } catch (err) {
    console.error('[ZrozumiloAI Embed] Streaming error:', err);
    store.updateLastAssistantMessage({ content: formatChatError(err) });
    updateMessages();
  } finally {
    store.setState({ isStreaming: false });
    render();
  }
}

/** Застосувати конфіг від батьківського віджета. */
async function applyConfig(nextConfig) {
  stopGreetingTypewriter();
  applyThemeColor(nextConfig.color);
  store.setState({
    config: nextConfig,
    initError: '',
    messages: [],
    typedGreeting: '',
  });

  render();
  try {
    const { workspace, model, initError } = await fetchWorkspaceConfig(nextConfig);
    store.setState({ workspace, model, initError });
  } catch (err) {
    store.setState({
      workspace: null,
      model: '',
      initError: err.message || 'Помилка ініціалізації чату',
    });
    console.error('[ZrozumiloAI Embed] fetchWorkspaceConfig error:', err);
  }
  render();
}

/** Слухач postMessage: приймає конфіг лише від довіреного origin. */
window.addEventListener('message', (event) => {
  if (event.data?.type !== 'zrozumiloai-config') {
    return;
  }
  const trustedOrigin = store.getState().trustedOrigin;
  if (trustedOrigin && event.origin !== trustedOrigin) {
    return;
  }
  store.setState({ trustedOrigin: event.origin });
  applyConfig(event.data.config).catch((err) => {
    console.error('[ZrozumiloAI Embed] applyConfig:', err);
  });
});

function notifyReady() {
  window.parent.postMessage({ type: 'zrozumiloai-ready' }, '*');
}

notifyReady();
render();

// Повторні запити конфігу, поки widget.js не відповість.
const readyRetry = setInterval(() => {
  if (store.getState().config) {
    clearInterval(readyRetry);
    return;
  }
  notifyReady();
}, 500);

// Таймаут, якщо конфіг не надійшов від widget.js.
setTimeout(() => {
  clearInterval(readyRetry);
  if (!store.getState().config && root) {
    root.innerHTML = '<div class="embed__status embed__status--error">Не вдалося завантажити конфігурацію чату.</div>';
  }
}, CONFIG_TIMEOUT_MS);

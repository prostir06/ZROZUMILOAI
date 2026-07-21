/**
 * Embed-чат у iframe: отримує конфіг від widget.js, спілкується з API.
 */
import './embed.css';
import {
  buildAuthHeader,
  EMBED_FAQ_QUESTIONS,
  EMBED_GREETING,
  escapeHtml,
  formatMessageContent,
  getEmbedStatusText,
  safeJson,
  sanitizeColor,
} from './utils.js';

const root = document.getElementById('embed-root');
const CONFIG_TIMEOUT_MS = 15000;
const ASSISTANT_ICON_URL = '/zrozumilo-assistant.png';

/** Іконка Помічника біля відповіді ШІ. */
function renderAssistantIcon() {
  return `<img src="${ASSISTANT_ICON_URL}" alt="" class="embed__assistant-icon" width="28" height="28" />`;
}

/** Обгортка для повідомлення асистента з іконкою. */
function wrapAssistantMessage(innerHtml) {
  return `
    <div class="embed__assistant">
      ${renderAssistantIcon()}
      ${innerHtml}
    </div>
  `;
}

let config = null;
let workspace = null;
let model = '';
let initError = '';
let messages = [];
let isStreaming = false;
let trustedOrigin = null;
let typedGreeting = '';
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
  if (greetingEl) {
    greetingEl.textContent = typedGreeting;
  }
  if (cursorEl) {
    cursorEl.hidden = typedGreeting.length >= EMBED_GREETING.length;
  }
}

/** Ефект друкування привітання при відкритті форми. */
function startGreetingTypewriter() {
  if (
    typewriterTimer
    || messages.length > 0
    || !model
    || typedGreeting.length >= EMBED_GREETING.length
  ) {
    return;
  }
  typedGreeting = '';
  let index = 0;
  typewriterTimer = setInterval(() => {
    if (index >= EMBED_GREETING.length) {
      stopGreetingTypewriter();
      updateGreetingElement();
      return;
    }
    typedGreeting += EMBED_GREETING[index];
    index += 1;
    updateGreetingElement();
  }, 28);
}

/** HTML хмари частих запитань (над полем вводу). */
function renderFaqCloud() {
  if (!model) {
    return '';
  }
  const chips = EMBED_FAQ_QUESTIONS.map(
    (question) => `
      <button
        type="button"
        class="embed__faq-chip"
        data-question="${escapeHtml(question)}"
        ${isStreaming ? 'disabled' : ''}
      >${escapeHtml(question)}</button>
    `,
  ).join('');

  return `
    <div class="embed__faq" role="group" aria-label="Часті запитання">
      ${chips}
    </div>
  `;
}

/** Підключити обробники кліків на часті запитання. */
function attachFaqHandlers() {
  root?.querySelectorAll('.embed__faq-chip').forEach((button) => {
    button.addEventListener('click', () => {
      handleSend(button.dataset.question || button.textContent || '');
    });
  });
}

/** Повний перерендер UI embed-чату. */
function render() {
  if (!root) {
    return;
  }

  if (!config) {
    root.innerHTML = '<div class="embed__status">Завантаження…</div>';
    return;
  }

  root.innerHTML = `
    <div class="embed">
      <header class="embed__header">
        <div>
          <div class="embed__title">${escapeHtml(config.title)}</div>
          ${workspace ? `<div class="embed__subtitle">${escapeHtml(workspace.name)}</div>` : ''}
        </div>
        <button type="button" class="embed__close" aria-label="Закрити">×</button>
      </header>
      <div class="embed__status ${!workspace || !model ? 'embed__status--error' : ''}" id="embed-status">
        ${getStatusText()}
      </div>
      <div class="embed__messages" id="embed-messages" role="log" aria-live="polite">
        ${renderMessages()}
      </div>
      <div class="embed__footer">
        ${renderFaqCloud()}
        <form class="embed__input-row" id="embed-form">
          <textarea
            id="embed-input"
            rows="1"
            placeholder="Напишіть повідомлення…"
            ${!model || isStreaming ? 'disabled' : ''}
          ></textarea>
          <button type="submit" class="embed__send" ${!model || isStreaming ? 'disabled' : ''}>
            Надіслати
          </button>
        </form>
      </div>
    </div>
  `;

  root.querySelector('.embed__close')?.addEventListener('click', () => {
    const targetOrigin = trustedOrigin || '*';
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

  attachFaqHandlers();

  if (messages.length === 0 && model) {
    updateGreetingElement();
    if (typedGreeting.length < EMBED_GREETING.length && !typewriterTimer) {
      startGreetingTypewriter();
    }
  }

  scrollToBottom();
}

/** Заголовок Authorization для API-запитів. */
function getAuthHeader() {
  return buildAuthHeader(config);
}

/** Текст статусу під заголовком чату. */
function getStatusText() {
  return getEmbedStatusText(config, workspace, model, initError);
}

/** HTML індикатора «Помічник друкує». */
function renderTypingIndicator() {
  return '<div class="embed__typing" aria-label="Помічник друкує"><span></span><span></span><span></span></div>';
}

/** HTML-розмітка списку повідомлень. */
function renderMessages() {
  if (messages.length === 0) {
    return `
      <div class="embed__welcome">
        ${wrapAssistantMessage(`
          <div class="embed__message embed__message--assistant">
            <span id="embed-greeting">${escapeHtml(typedGreeting)}</span><span
              id="embed-greeting-cursor"
              class="embed__cursor"
              aria-hidden="true"
            >|</span>
          </div>
        `)}
      </div>
    `;
  }

  const html = messages.map((msg, index) => {
    const isPendingAssistant = (
      isStreaming
      && index === messages.length - 1
      && msg.role === 'assistant'
      && !msg.content.trim()
    );

    if (isPendingAssistant) {
      return wrapAssistantMessage(renderTypingIndicator());
    }

    const bubble = `
      <div class="embed__message embed__message--${msg.role}">
        ${formatMessageContent(msg.content, msg.role)}
        ${msg.role === 'assistant' && Array.isArray(msg.sources) && msg.sources.length
          ? `<div class="embed__sources"><div class="embed__sources-title">Джерела</div><ul>${
            msg.sources.map((source) => (
              `<li><strong>${escapeHtml(source.document_name || 'Документ')}</strong>${
                source.excerpt
                  ? ` — ${escapeHtml(source.excerpt)}`
                  : ''
              }</li>`
            )).join('')
          }</ul></div>`
          : ''}
        ${msg.role === 'assistant' && msg.needsHandoff
          ? '<div class="embed__handoff">Якщо відповідь не допомогла — зверніться до підтримки курсу.</div>'
          : ''}
      </div>
    `;
    if (msg.role === 'assistant') {
      return wrapAssistantMessage(bubble);
    }
    return bubble;
  }).join('');

  const lastMessage = messages[messages.length - 1];
  const showStandaloneTyping = isStreaming && lastMessage?.role !== 'assistant';

  const typing = showStandaloneTyping
    ? wrapAssistantMessage(renderTypingIndicator())
    : '';

  return html + typing;
}

/** Прокрутка до останнього повідомлення. */
function scrollToBottom() {
  const container = root?.querySelector('#embed-messages');
  if (container) {
    container.scrollTop = container.scrollHeight;
  }
}

/** Оновлення лише блоку повідомлень (без повного render). */
function updateMessages() {
  const container = root?.querySelector('#embed-messages');
  if (!container) {
    return;
  }

  // P0: stick-to-bottom — не стрибати, якщо користувач прокрутив вгору.
  const distance = container.scrollHeight - container.scrollTop - container.clientHeight;
  const wasNearBottom = distance <= 80;

  container.innerHTML = renderMessages();

  if (wasNearBottom) {
    container.scrollTop = container.scrollHeight;
  }
}

/** Дописати текст у останній бульбашці асистента без повного rewrite списку. */
function appendToLastAssistant(text) {
  const container = root?.querySelector('#embed-messages');
  if (!container) {
    updateMessages();
    return;
  }
  const bubbles = container.querySelectorAll('.embed__message--assistant');
  const last = bubbles[bubbles.length - 1];
  if (!last) {
    updateMessages();
    return;
  }
  // formatBoldTextHtml потрібен для повного тексту — для stream додаємо escaped.
  last.insertAdjacentText('beforeend', text);
  const distance = container.scrollHeight - container.scrollTop - container.clientHeight;
  if (distance <= 80) {
    container.scrollTop = container.scrollHeight;
  }
}

/** HTTP-запит до backend API. */
async function apiRequest(path, options = {}) {
  try {
    const response = await fetch(`${config.apiUrl}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Authorization: getAuthHeader(),
        ...options.headers,
      },
    });
    return response;
  } catch (error) {
    throw new Error(error.message || 'Помилка мережі');
  }
}

/** Завантажити workspace і модель за токеном або API-ключем. */
async function initWorkspace() {
  initError = '';

  if (config.widgetToken) {
    const response = await apiRequest('/widget/config/');
    if (!response.ok) {
      const error = await safeJson(response);
      initError = error.error || error.detail || `Помилка конфігурації (${response.status})`;
      workspace = null;
      model = '';
      return;
    }
    const data = await safeJson(response);
    workspace = data.workspace || null;
    model = data.model || workspace?.model_names?.[0] || '';
    if (!workspace) {
      initError = 'Widget token недійсний або workspace недоступний.';
    }
    return;
  }

  const response = await apiRequest('/workspaces/my/');
  if (!response.ok) {
    const error = await safeJson(response);
    initError = error.error || error.detail || `Помилка завантаження workspace (${response.status})`;
    workspace = null;
    model = '';
    return;
  }

  const workspaces = await safeJson(response, []);
  workspace = workspaces.find(
    (item) => item.name === config.workspaceName,
  ) || null;

  model = workspace?.model_names?.[0] || '';
  if (!workspace) {
    initError = `Workspace «${config.workspaceName}» не знайдено.`;
  }
}

/** SSE-стрімінг відповіді чату. */
async function chatStream(chatMessages, onChunk) {
  if (!workspace?.id && !config.widgetToken) {
    throw new Error('Workspace не завантажено');
  }

  const chatPath = config.widgetToken ? '/widget/chat/' : '/ollama/chat/';
  const body = config.widgetToken
    ? { stream: true, messages: chatMessages }
    : {
      model,
      workspace_id: workspace.id,
      stream: true,
      messages: chatMessages,
    };

  if (config.openedxCourseId) {
    body.openedx_course_id = config.openedxCourseId;
  }

  const response = await apiRequest(chatPath, {
    method: 'POST',
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await safeJson(response);
    const message = error.error || error.detail || 'Помилка чату';
    throw new Error(message);
  }

  if (!response.body) {
    throw new Error('Порожня відповідь сервера');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  let doneReading = false;
  while (!doneReading) {
    const { done, value } = await reader.read();
    doneReading = done;
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) {
        continue;
      }
      try {
        const data = JSON.parse(line.slice(6));
        onChunk(data);
      } catch {
        /* пропускаємо пошкоджені SSE-чанки */
      }
    }
  }
}

/** Обробка надсилання повідомлення користувачем. */
async function handleSend(text) {
  const content = text.trim();
  if (!content || !model || !workspace || isStreaming) {
    return;
  }

  stopGreetingTypewriter();
  typedGreeting = EMBED_GREETING;

  messages = [...messages, { role: 'user', content }];
  isStreaming = true;
  render();

  const chatMessages = messages.map((msg) => ({ role: msg.role, content: msg.content }));
  messages = [...messages, { role: 'assistant', content: '' }];
  updateMessages();

  try {
    await chatStream(chatMessages, (chunk) => {
      // Спочатку текст (append DOM), потім meta — щоб updateMessages не затирав стрім.
      if (chunk.message?.content) {
        messages = messages.map((msg, index) => {
          if (index === messages.length - 1 && msg.role === 'assistant') {
            return { ...msg, content: msg.content + chunk.message.content };
          }
          return msg;
        });
        appendToLastAssistant(chunk.message.content);
      }
      if (chunk.error) {
        messages = messages.map((msg, index) => {
          if (index === messages.length - 1 && msg.role === 'assistant') {
            return { ...msg, content: `Помилка: ${chunk.error}` };
          }
          return msg;
        });
        updateMessages();
      }
      if (chunk.sources || chunk.log_id != null || typeof chunk.needs_handoff === 'boolean') {
        messages = messages.map((msg, index) => {
          if (index !== messages.length - 1 || msg.role !== 'assistant') {
            return msg;
          }
          return {
            ...msg,
            ...(chunk.sources ? { sources: chunk.sources } : {}),
            ...(chunk.log_id != null ? { logId: chunk.log_id } : {}),
            ...(typeof chunk.needs_handoff === 'boolean'
              ? { needsHandoff: chunk.needs_handoff }
              : {}),
          };
        });
        // Повний rewrite потрібен для блоку «Джерела» / handoff hint.
        updateMessages();
      }
    });
  } catch (err) {
    messages = messages.map((msg, index) => {
      if (index === messages.length - 1 && msg.role === 'assistant') {
        return { ...msg, content: `Помилка: ${err.message}` };
      }
      return msg;
    });
    updateMessages();
  } finally {
    isStreaming = false;
    render();
  }
}

/** Застосувати конфіг від батьківського віджета. */
async function applyConfig(nextConfig) {
  config = nextConfig;
  initError = '';
  messages = [];
  typedGreeting = '';
  stopGreetingTypewriter();
  document.documentElement.style.setProperty('--color-primary', sanitizeColor(config.color));
  document.documentElement.style.setProperty('--color-user', sanitizeColor(config.color));

  render();
  try {
    await initWorkspace();
  } catch (err) {
    workspace = null;
    model = '';
    initError = err.message || 'Помилка ініціалізації чату';
    console.error('[ZrozumiloAI Embed] initWorkspace:', err);
  }
  render();
}

/** Слухач postMessage: приймає конфіг лише від довіреного origin. */
window.addEventListener('message', (event) => {
  if (event.data?.type !== 'zrozumiloai-config') {
    return;
  }
  if (trustedOrigin && event.origin !== trustedOrigin) {
    return;
  }
  trustedOrigin = event.origin;
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
  if (config) {
    clearInterval(readyRetry);
    return;
  }
  notifyReady();
}, 500);

// Таймаут, якщо конфіг не надійшов від widget.js.
setTimeout(() => {
  clearInterval(readyRetry);
  if (!config && root) {
    root.innerHTML = '<div class="embed__status embed__status--error">Не вдалося завантажити конфігурацію чату.</div>';
  }
}, CONFIG_TIMEOUT_MS);

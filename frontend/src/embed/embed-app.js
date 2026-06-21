/**
 * Embed-чат у iframe: отримує конфіг від widget.js, спілкується з API.
 */
import './embed.css';

const root = document.getElementById('embed-root');
const CONFIG_TIMEOUT_MS = 15000;

let config = null;
let workspace = null;
let model = '';
let messages = [];
let isStreaming = false;
let trustedOrigin = null;

/** Екранування HTML для безпечного рендеру тексту. */
function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/** Підтримка **жирного** тексту в відповідях асистента. */
function formatBoldTextHtml(text) {
  if (!text) {
    return '';
  }
  const escaped = escapeHtml(text);
  return escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
}

/** Форматування вмісту повідомлення залежно від ролі. */
function formatMessageContent(text, role) {
  if (role === 'assistant') {
    return formatBoldTextHtml(text);
  }
  return escapeHtml(text);
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

  scrollToBottom();
}

/** Заголовок Authorization для API-запитів. */
function getAuthHeader() {
  if (config.widgetToken) {
    return `Widget-Token ${config.widgetToken}`;
  }
  return `Api-Key ${config.apiKey}`;
}

/** Текст статусу під заголовком чату. */
function getStatusText() {
  if (!workspace) {
    if (config.widgetToken) {
      return 'Widget token недійсний або workspace недоступний.';
    }
    return `Workspace «${escapeHtml(config.workspaceName)}» не знайдено. Перевірте API-ключ та data-workspace.`;
  }
  if (!model) {
    return 'Модель не налаштована для цього workspace.';
  }
  return `Модель: ${model}`;
}

/** HTML-розмітка списку повідомлень. */
function renderMessages() {
  if (messages.length === 0) {
    return '<div class="embed__empty">Привіт! Чим можемо допомогти?</div>';
  }

  const html = messages.map((msg) => `
    <div class="embed__message embed__message--${msg.role}">
      ${formatMessageContent(msg.content, msg.role)}
    </div>
  `).join('');

  const typing = isStreaming
    ? '<div class="embed__typing" aria-label="Помічник друкує"><span></span><span></span><span></span></div>'
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
  if (container) {
    container.innerHTML = renderMessages();
    scrollToBottom();
  }
}

/** Безпечний парсинг JSON з fetch-відповіді. */
async function safeJson(response, fallback = {}) {
  try {
    return await response.json();
  } catch {
    return fallback;
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
  if (config.widgetToken) {
    const response = await apiRequest('/widget/config/');
    if (!response.ok) {
      workspace = null;
      model = '';
      return;
    }
    const data = await safeJson(response);
    workspace = data.workspace || null;
    model = data.model || workspace?.model_names?.[0] || '';
    return;
  }

  const response = await apiRequest('/workspaces/my/');
  if (!response.ok) {
    workspace = null;
    return;
  }

  const workspaces = await safeJson(response, []);
  workspace = workspaces.find(
    (item) => item.name === config.workspaceName,
  ) || null;

  model = workspace?.model_names?.[0] || '';
}

/** SSE-стрімінг відповіді чату. */
async function chatStream(chatMessages, onChunk) {
  const chatPath = config.widgetToken ? '/widget/chat/' : '/ollama/chat/';
  const body = config.widgetToken
    ? { stream: true, messages: chatMessages }
    : {
      model,
      workspace_id: workspace.id,
      stream: true,
      messages: chatMessages,
    };

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
  if (!content || !model || isStreaming) {
    return;
  }

  messages = [...messages, { role: 'user', content }];
  isStreaming = true;
  render();

  const chatMessages = messages.map((msg) => ({ role: msg.role, content: msg.content }));
  messages = [...messages, { role: 'assistant', content: '' }];
  updateMessages();

  try {
    await chatStream(chatMessages, (chunk) => {
      if (chunk.message?.content) {
        messages = messages.map((msg, index) => {
          if (index === messages.length - 1 && msg.role === 'assistant') {
            return { ...msg, content: msg.content + chunk.message.content };
          }
          return msg;
        });
        updateMessages();
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
  document.documentElement.style.setProperty('--color-primary', config.color || '#0D9E96');
  document.documentElement.style.setProperty('--color-user', config.color || '#0D9E96');

  render();
  try {
    await initWorkspace();
  } catch (err) {
    workspace = null;
    model = '';
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

// Повідомляємо батьківську сторінку про готовність iframe.
window.parent.postMessage({ type: 'zrozumiloai-ready' }, '*');
render();

// Таймаут, якщо конфіг не надійшов від widget.js.
setTimeout(() => {
  if (!config && root) {
    root.innerHTML = '<div class="embed__status embed__status--error">Не вдалося завантажити конфігурацію чату.</div>';
  }
}, CONFIG_TIMEOUT_MS);

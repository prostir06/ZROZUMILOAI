import {
  escapeHtml,
  formatMessageContent,
  getEmbedStatusText,
  readEmbedFeedbackClick,
  sanitizeColor,
} from './utils.js';

export const ASSISTANT_ICON_URL = '/zrozumilo-assistant.png';

/** Іконка Помічника біля відповіді ШІ. */
export function renderAssistantIcon() {
  return `<img src="${ASSISTANT_ICON_URL}" alt="" class="embed__assistant-icon" width="28" height="28" />`;
}

/** Обгортка для повідомлення асистента з іконкою. */
export function wrapAssistantMessage(innerHtml) {
  return `
    <div class="embed__assistant">
      ${renderAssistantIcon()}
      ${innerHtml}
    </div>
  `;
}

/** HTML індикатора «Помічник друкує». */
export function renderTypingIndicator() {
  return '<div class="embed__typing" aria-label="Помічник друкує"><span></span><span></span><span></span></div>';
}

/** HTML хмари частих запитань (над полем вводу). */
export function renderFaqCloud({ model, isStreaming = false, questions = [] }) {
  if (!model || questions.length === 0) {
    return '';
  }
  const chips = questions.map(
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

/** HTML-розмітка списку повідомлень або екрану привітання. */
export function renderMessages({ messages = [], isStreaming = false, typedGreeting = '' }) {
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
        ${msg.role === 'assistant' && msg.needsHandoff
          ? '<div class="embed__handoff">Якщо відповідь не допомогла — зверніться до підтримки курсу.</div>'
          : ''}
        ${msg.role === 'assistant' && msg.logId && !isStreaming
          ? `<div class="embed__feedback" data-log-id="${msg.logId}">
              <button type="button" class="embed__feedback-btn" data-feedback="up" aria-label="Корисна відповідь" aria-pressed="${msg.feedback === 'up' ? 'true' : 'false'}">👍</button>
              <button type="button" class="embed__feedback-btn" data-feedback="down" aria-label="Некорисна відповідь" aria-pressed="${msg.feedback === 'down' ? 'true' : 'false'}">👎</button>
              ${!msg.needsHandoff
                ? '<button type="button" class="embed__feedback-btn" data-handoff="1" aria-label="Запросити допомогу людини">До людини</button>'
                : ''}
            </div>`
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

/** HTML заголовка віджета. */
export function renderHeader({ config, workspace }) {
  return `
    <header class="embed__header">
      <div>
        <div class="embed__title">${escapeHtml(config?.title || 'Підтримка')}</div>
        ${workspace ? `<div class="embed__subtitle">${escapeHtml(workspace.name)}</div>` : ''}
      </div>
      <button type="button" class="embed__close" aria-label="Закрити">×</button>
    </header>
  `;
}

/** HTML блоку статусу віджета. */
export function renderStatus({ config, workspace, model, initError }) {
  const isError = !workspace || !model;
  return `
    <div class="embed__status ${isError ? 'embed__status--error' : ''}" id="embed-status">
      ${getEmbedStatusText(config, workspace, model, initError)}
    </div>
  `;
}

/** Повний HTML каркас embed-чату. */
export function renderEmbedLayout(state) {
  const {
    config,
    workspace,
    model,
    initError,
    messages = [],
    isStreaming = false,
    typedGreeting = '',
    questions = [],
  } = state;

  if (!config) {
    return '<div class="embed__status">Завантаження…</div>';
  }

  return `
    <div class="embed">
      ${renderHeader({ config, workspace })}
      ${renderStatus({ config, workspace, model, initError })}
      <div class="embed__messages" id="embed-messages" role="log" aria-live="polite">
        ${renderMessages({ messages, isStreaming, typedGreeting })}
      </div>
      <div class="embed__footer">
        ${renderFaqCloud({ model, isStreaming, questions })}
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
}

/** Застосувати колір теми до CSS Custom Properties. */
export function applyThemeColor(color) {
  if (typeof document === 'undefined') {
    return;
  }
  const sanitized = sanitizeColor(color);
  document.documentElement.style.setProperty('--color-primary', sanitized);
  document.documentElement.style.setProperty('--color-user', sanitized);
}

/** Перевірка близькості скролу до низу. */
export function isNearBottom(container, threshold = 80) {
  if (!container) {
    return false;
  }
  const distance = container.scrollHeight - container.scrollTop - container.clientHeight;
  return distance <= threshold;
}

/** Прокрутка контейнера до низу. */
export function scrollToBottom(container) {
  if (container) {
    container.scrollTop = container.scrollHeight;
  }
}

/** Дописати текст у останню бульбашку асистента зі збереженням stick-to-bottom. */
export function appendAssistantText(container, text) {
  if (!container) {
    return false;
  }
  if (container.querySelector('.embed__typing')) {
    return false;
  }
  const bubbles = container.querySelectorAll('.embed__message--assistant');
  const last = bubbles[bubbles.length - 1];
  if (!last) {
    return false;
  }
  last.insertAdjacentText('beforeend', text);
  if (isNearBottom(container)) {
    scrollToBottom(container);
  }
  return true;
}

/** Підключити обробники кліків на часті запитання. */
export function attachFaqListeners(root, onSelectQuestion) {
  root?.querySelectorAll('.embed__faq-chip').forEach((button) => {
    button.addEventListener('click', () => {
      onSelectQuestion(button.dataset.question || button.textContent || '');
    });
  });
}

/** Підключити обробники оцінок 👍 / 👎 / «До людини». */
export function attachFeedbackListeners(container, onFeedback) {
  container?.querySelectorAll('.embed__feedback').forEach((block) => {
    block.onclick = (event) => {
      const parsed = readEmbedFeedbackClick(event.target, block);
      if (!parsed) {
        return;
      }
      onFeedback(parsed.logId, parsed.payload);
    };
  });
}

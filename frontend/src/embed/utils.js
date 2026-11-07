/** Привітання embed-віджета при відкритті. */
export const EMBED_GREETING = 'Вітаю! Я Помічник на платформі Зрозуміло!';

/** Часті запитання у хмарі швидких кнопок embed-чату. */
export const EMBED_FAQ_QUESTIONS = [
  'Як зареєструватися?',
  'Як отримати сертифікат?',
  'Чи має Зрозуміло! акредитацію або ліцензію?',
];

/** Дозволити лише hex-колір для CSS custom properties. */
export function sanitizeColor(color) {
  const value = String(color || '').trim();
  if (/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(value)) {
    return value;
  }
  return '#0D9E96';
}

/** Прибрати небезпечні символи з текстового заголовка. */
export function sanitizeTitle(title) {
  const value = String(title || 'Підтримка').trim();
  const cleaned = value.replace(/[<>"']/g, '');
  return cleaned.slice(0, 80) || 'Підтримка';
}

/** Екранування HTML для безпечного рендеру тексту. */
export function escapeHtml(text) {
  if (text == null || text === '') {
    return '';
  }
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/** Підтримка **жирного** тексту в відповідях асистента. */
export function formatBoldTextHtml(text) {
  if (!text) {
    return '';
  }
  const escaped = escapeHtml(text);
  return escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
}

/** Форматування вмісту повідомлення залежно від ролі. */
export function formatMessageContent(text, role) {
  if (role === 'assistant') {
    return formatBoldTextHtml(text);
  }
  return escapeHtml(text);
}

export { truncateText } from '../utils/text.js';

/** Безпечний парсинг JSON з fetch Response (для embed API). */
export async function safeJson(response, fallback = {}) {
  try {
    return await response.json();
  } catch (err) {
    console.warn('[ZrozumiloAI Embed] JSON parse failed:', err);
    return fallback;
  }
}

/** Перевірка, що рядок містить лише ISO-8859-1 (ByteString) символи (код <= 255). */
export function isIso88591(str) {
  if (typeof str !== 'string') return true;
  for (let i = 0; i < str.length; i++) {
    if (str.charCodeAt(i) > 255) return false;
  }
  return true;
}

/** Текст Authorization для widget token або API key. */
export function buildAuthHeader(config) {
  if (!config) {
    return '';
  }
  if (config.widgetToken) {
    const token = String(config.widgetToken).trim();
    if (!isIso88591(token)) {
      return '';
    }
    return `Widget-Token ${token}`;
  }
  if (config.apiKey) {
    const key = String(config.apiKey).trim();
    if (!isIso88591(key)) {
      return '';
    }
    return `Api-Key ${key}`;
  }
  return '';
}

/** Текст статусу embed-чату залежно від workspace/model. */
export function getEmbedStatusText(config, workspace, model, initError = '') {
  if (initError) {
    return escapeHtml(initError);
  }
  if (!config) {
    return '';
  }
  if (!workspace) {
    if (config.widgetToken) {
      return 'Widget token недійсний або workspace недоступний.';
    }
    const name = escapeHtml(config.workspaceName || '');
    return `Workspace «${name}» не знайдено. Перевірте API-ключ та data-workspace.`;
  }
  if (!model) {
    return 'Модель не налаштована для цього workspace.';
  }
  return `Модель: ${escapeHtml(model)}`;
}

/**
 * Розбір кліку по feedback-кнопці embed.
 * Повертає null, якщо клік не по кнопці або немає log id.
 */
export function readEmbedFeedbackClick(target, block) {
  const btn = target?.closest?.('[data-feedback],[data-handoff]');
  if (!btn || !block) {
    return null;
  }
  const logId = Number(block.getAttribute('data-log-id'));
  if (!logId) {
    return null;
  }
  const payload = {};
  if (btn.hasAttribute('data-feedback')) {
    payload.feedback = btn.getAttribute('data-feedback');
  }
  if (btn.hasAttribute('data-handoff')) {
    payload.needs_handoff = true;
  }
  if (!payload.feedback && !payload.needs_handoff) {
    return null;
  }
  return { logId, payload };
}

/**
 * Утиліти embed-чату: екранування HTML та форматування тексту.
 */

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

/** Скоротити текст для превʼю в таблиці. */
export function truncateText(text, maxLength) {
  if (!text || text.length <= maxLength) {
    return text || '—';
  }
  return `${text.slice(0, maxLength)}…`;
}

/** Безпечний парсинг JSON з fetch Response (для embed API). */
export async function safeJson(response, fallback = {}) {
  try {
    return await response.json();
  } catch {
    return fallback;
  }
}

/** Текст Authorization для widget token або API key. */
export function buildAuthHeader(config) {
  if (!config) {
    return '';
  }
  if (config.widgetToken) {
    return `Widget-Token ${config.widgetToken}`;
  }
  if (config.apiKey) {
    return `Api-Key ${config.apiKey}`;
  }
  return '';
}

/** Текст статусу embed-чату залежно від workspace/model. */
export function getEmbedStatusText(config, workspace, model, initError = '') {
  if (initError) {
    return initError;
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
  return `Модель: ${model}`;
}

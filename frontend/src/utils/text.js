/** Спільні текстові утиліти (admin + embed). */

/** Скоротити текст для превʼю в таблиці. */
export function truncateText(text, maxLength) {
  if (!text || text.length <= maxLength) {
    return text || '—';
  }
  return `${text.slice(0, maxLength)}…`;
}

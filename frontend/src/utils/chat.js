/**
 * Утиліти для відображення чатів у sidebar.
 */

/** Побудувати заголовок чату з першого повідомлення (до 60 символів). */
export function buildChatTitle(text) {
  const trimmed = String(text || '').trim();
  if (!trimmed) {
    return 'Новий чат';
  }
  return trimmed.length > 60 ? `${trimmed.slice(0, 60)}…` : trimmed;
}

/** Форматувати дату чату українською (сьогодні — час, інакше — дата). */
export function formatChatDate(iso) {
  if (!iso) {
    return '';
  }

  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return '';
  }

  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();
  if (isToday) {
    return date.toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' });
  }
  return date.toLocaleDateString('uk-UA', { day: 'numeric', month: 'short' });
}

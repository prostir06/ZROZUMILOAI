export function buildChatTitle(text) {
  const trimmed = text.trim();
  if (!trimmed) return 'Новий чат';
  return trimmed.length > 60 ? `${trimmed.slice(0, 60)}…` : trimmed;
}

export function formatChatDate(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();
  if (isToday) {
    return date.toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' });
  }
  return date.toLocaleDateString('uk-UA', { day: 'numeric', month: 'short' });
}

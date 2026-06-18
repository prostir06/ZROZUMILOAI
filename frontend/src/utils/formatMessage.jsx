/**
 * Перетворює **текст** на жирний шрифт у повідомленнях AI.
 */
export function formatBoldText(text) {
  if (!text) return text;

  const parts = [];
  const regex = /\*\*(.+?)\*\*/g;
  let lastIndex = 0;
  let match = regex.exec(text);
  let key = 0;

  while (match !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(<strong key={key}>{match[1]}</strong>);
    key += 1;
    lastIndex = regex.lastIndex;
    match = regex.exec(text);
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : text;
}

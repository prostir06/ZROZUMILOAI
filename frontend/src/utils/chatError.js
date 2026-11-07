export function formatChatError(err) {
  if (err?.code === 'ollama_busy') {
    return err.message || 'Модель зайнята. Спробуйте ще раз за хвилину.';
  }
  return `Помилка: ${err?.message || 'Помилка чату'}`;
}

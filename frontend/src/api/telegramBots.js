import { safeJson } from '../utils/safeJson.js';
import { api } from './client.js';

export async function getTelegramBots() {
  const response = await api.request('/telegram-bots/');
  if (!response.ok) {
    const error = await safeJson(response, {});
    throw new Error(error.detail || error.error || 'Не вдалося отримати список телеграм-ботів');
  }
  return response.json();
}

export async function createTelegramBot(data) {
  const response = await api.request('/telegram-bots/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await safeJson(response, {});
    throw new Error(
      error.token?.[0]
      || error.name?.[0]
      || error.workspace?.[0]
      || error.detail
      || error.error
      || Object.values(error).flat()[0]
      || 'Не вдалося створити телеграм-бота',
    );
  }
  return response.json();
}

export async function updateTelegramBot(id, data) {
  const response = await api.request(`/telegram-bots/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await safeJson(response, {});
    throw new Error(
      error.token?.[0]
      || error.name?.[0]
      || error.workspace?.[0]
      || error.detail
      || error.error
      || Object.values(error).flat()[0]
      || 'Не вдалося оновити телеграм-бота',
    );
  }
  return response.json();
}

export async function deleteTelegramBot(id) {
  const response = await api.request(`/telegram-bots/${id}/`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const error = await safeJson(response, {});
    throw new Error(error.detail || error.error || 'Не вдалося видалити телеграм-бота');
  }
  return true;
}

export async function verifyTelegramBot(id) {
  const response = await api.request(`/telegram-bots/${id}/verify/`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await safeJson(response, {});
    throw new Error(error.error || error.detail || 'Не вдалося перевірити токен телеграм-бота');
  }
  return response.json();
}

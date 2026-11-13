import { safeJson } from '../utils/safeJson.js';
import { api } from './client.js';

function extractErrorMessage(error, fallback) {
  if (!error) return fallback;
  if (typeof error === 'string') return error;
  if (Array.isArray(error)) return error[0] || fallback;
  const fieldMsg = error.token?.[0]
    || error.name?.[0]
    || error.workspace?.[0]
    || (typeof error.detail === 'string' ? error.detail : null)
    || (typeof error.error === 'string' ? error.error : null);
  if (fieldMsg) return fieldMsg;
  if (typeof error === 'object') {
    const first = Object.values(error).flat()[0];
    if (typeof first === 'string') return first;
  }
  return fallback;
}

export async function getTelegramBots() {
  const response = await api.request('/telegram-bots/');
  if (!response.ok) {
    const error = await safeJson(response, {});
    throw new Error(extractErrorMessage(error, 'Не вдалося отримати список телеграм-ботів'));
  }
  const data = await safeJson(response, null);
  if (data === null) {
    throw new Error('Некоректна відповідь сервера (очікувався JSON)');
  }
  return data;
}

export async function createTelegramBot(data) {
  const response = await api.request('/telegram-bots/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await safeJson(response, {});
    throw new Error(extractErrorMessage(error, 'Не вдалося створити телеграм-бота'));
  }
  const result = await safeJson(response, null);
  if (result === null) {
    throw new Error('Некоректна відповідь сервера (очікувався JSON)');
  }
  return result;
}

export async function updateTelegramBot(id, data) {
  const response = await api.request(`/telegram-bots/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await safeJson(response, {});
    throw new Error(extractErrorMessage(error, 'Не вдалося оновити телеграм-бота'));
  }
  const result = await safeJson(response, null);
  if (result === null) {
    throw new Error('Некоректна відповідь сервера (очікувався JSON)');
  }
  return result;
}

export async function deleteTelegramBot(id) {
  const response = await api.request(`/telegram-bots/${id}/`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const error = await safeJson(response, {});
    throw new Error(extractErrorMessage(error, 'Не вдалося видалити телеграм-бота'));
  }
  return true;
}

export async function verifyTelegramBot(id) {
  const response = await api.request(`/telegram-bots/${id}/verify/`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await safeJson(response, {});
    throw new Error(extractErrorMessage(error, 'Не вдалося перевірити токен телеграм-бота'));
  }
  const result = await safeJson(response, null);
  if (result === null) {
    throw new Error('Некоректна відповідь сервера (очікувався JSON)');
  }
  return result;
}

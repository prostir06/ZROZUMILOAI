import { safeJson } from '../utils/safeJson.js';

function extractTelegramMutationError(error, fallback) {
  return error.token?.[0]
    || error.name?.[0]
    || error.workspace?.[0]
    || error.detail
    || error.error
    || Object.values(error).flat()[0]
    || fallback;
}

async function parseJsonOrThrow(response) {
  const data = await safeJson(response, null);
  if (data === null) {
    throw new Error('Некоректна відповідь сервера (очікувався JSON)');
  }
  return data;
}

export const telegramApiMethods = {
  async getTelegramBots() {
    const response = await this.request('/telegram-bots/');
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.detail || error.error || 'Не вдалося отримати список телеграм-ботів');
    }
    return parseJsonOrThrow(response);
  },

  async createTelegramBot(data) {
    const response = await this.request('/telegram-bots/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(extractTelegramMutationError(error, 'Не вдалося створити телеграм-бота'));
    }
    return parseJsonOrThrow(response);
  },

  async updateTelegramBot(botId, data) {
    const response = await this.request(`/telegram-bots/${botId}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(extractTelegramMutationError(error, 'Не вдалося оновити телеграм-бота'));
    }
    return parseJsonOrThrow(response);
  },

  async deleteTelegramBot(botId) {
    const response = await this.request(`/telegram-bots/${botId}/`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.detail || error.error || 'Не вдалося видалити телеграм-бота');
    }
    return true;
  },

  async verifyTelegramBot(botId) {
    const response = await this.request(`/telegram-bots/${botId}/verify/`, {
      method: 'POST',
    });
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.error || error.detail || 'Не вдалося перевірити токен телеграм-бота');
    }
    return parseJsonOrThrow(response);
  },
};

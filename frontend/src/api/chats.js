import { safeJson } from '../utils/safeJson.js';

function appendChatLogFilterParams(params, {
  needsHandoff,
  needs_handoff,
  feedback,
  workspace_id,
  workspaceId,
  range,
  channel,
} = {}) {
  const handoff = needsHandoff !== undefined ? needsHandoff : needs_handoff;
  if (handoff === true) params.set('needs_handoff', 'true');
  if (handoff === false) params.set('needs_handoff', 'false');
  if (feedback !== undefined && feedback !== null) {
    params.set('feedback', feedback);
  }
  const ws = workspace_id ?? workspaceId;
  if (ws) {
    params.set('workspace_id', String(ws));
  }
  if (range && range !== 'all') {
    params.set('range', range);
  }
  if (channel && channel !== 'all') {
    params.set('channel', channel);
  }
}

export const chatApiMethods = {
  /**
   * Відгук на відповідь чату (up/down) або запит handoff.
   * @param {number} logId — id WorkspaceChatLog зі стріму (поле log_id)
   * @param {{ feedback?: string, needs_handoff?: boolean }} payload
   */
  async submitChatFeedback(logId, { feedback, needs_handoff } = {}) {
    const body = {};
    if (feedback !== undefined) body.feedback = feedback;
    if (needs_handoff !== undefined) body.needs_handoff = needs_handoff;
    const response = await this.request(`/chats/logs/${logId}/feedback/`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.error || 'Не вдалося надіслати відгук');
    }
    return response.json();
  },

  async getChats() {
    const response = await this.request('/chats/');
    if (!response.ok) throw new Error('Не вдалося отримати чати');
    return response.json();
  },

  async getChat(chatId) {
    const response = await this.request(`/chats/${chatId}/`);
    if (!response.ok) throw new Error('Не вдалося отримати чат');
    return response.json();
  },

  async createChat(data) {
    const response = await this.request('/chats/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.detail || 'Не вдалося створити чат');
    }
    return response.json();
  },

  async updateChat(chatId, data) {
    const response = await this.request(`/chats/${chatId}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.detail || 'Не вдалося оновити чат');
    }
    return response.json();
  },

  async deleteChat(chatId) {
    const response = await this.request(`/chats/${chatId}/`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Не вдалося видалити чат');
    return true;
  },

  async analyzeWorkspaceChatLogs(payload = {}) {
    const response = await this.request('/chats/logs/analysis/', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    const data = await safeJson(response, {});
    if (!response.ok) {
      const err = new Error(data.error || data.detail || 'Не вдалося проаналізувати таблицю');
      err.code = data.code || '';
      throw err;
    }
    return data;
  },

  async getWorkspaceChatLogs({
    needsHandoff,
    feedback,
    limit = 50,
    offset = 0,
    workspace_id,
    workspaceId,
    range,
    channel,
  } = {}) {
    const params = new URLSearchParams();
    params.set('limit', String(limit));
    params.set('offset', String(offset));
    appendChatLogFilterParams(params, {
      needsHandoff,
      feedback,
      workspace_id,
      workspaceId,
      range,
      channel,
    });
    const response = await this.request(`/chats/logs/?${params.toString()}`);
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.error || error.detail || 'Не вдалося отримати логи чатів');
    }
    const data = await safeJson(response, {});
    // Підтримка старого формату (масив) і нового { results, count }.
    if (Array.isArray(data)) {
      return { count: data.length, results: data, limit, offset: 0 };
    }
    return {
      count: data.count || 0,
      results: data.results || [],
      limit: data.limit ?? limit,
      offset: data.offset ?? offset,
    };
  },

  async deleteWorkspaceChatLog(logId) {
    const response = await this.request(`/chats/logs/${logId}/`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.error || error.detail || 'Не вдалося видалити чат log');
    }
    return safeJson(response, {});
  },

  async clearWorkspaceChatLogs() {
    const response = await this.request('/chats/logs/clear/', {
      method: 'DELETE',
    });
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.error || error.detail || 'Не вдалося очистити логи чатів');
    }
    return safeJson(response, {});
  },

  getWorkspaceChatLogsExportUrl(format, filters = {}) {
    const params = new URLSearchParams();
    params.set('export_format', format);
    appendChatLogFilterParams(params, filters);
    return `${this.baseUrl}/chats/logs/export/?${params.toString()}`;
  },

  async exportWorkspaceChatLogs(format, filters = {}) {
    const token = this.getToken();
    const url = this.getWorkspaceChatLogsExportUrl(format, filters);
    const response = await fetch(
      url,
      { headers: { Authorization: `Bearer ${token}` } },
    );

    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.error || error.detail || 'Не вдалося експортувати логи чатів');
    }

    const blob = await response.blob();
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match?.[1] || `workspace_chats.${format}`;
    const urlObj = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = urlObj;
    link.download = filename;
    link.click();
    window.URL.revokeObjectURL(urlObj);
  },
};

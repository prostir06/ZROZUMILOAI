import { safeJson } from '../utils/safeJson.js';

export const ollamaApiMethods = {
  async getOllamaHealth() {
    const response = await this.request('/ollama/health/');
    if (!response.ok) {
      return { connected: false };
    }
    return safeJson(response, { connected: false });
  },

  async getModels() {
    const response = await this.request('/ollama/models/');
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.error || 'Не вдалося отримати моделі');
    }
    return response.json();
  },

  async deleteModel(name) {
    const response = await this.request('/ollama/models/delete/', {
      method: 'DELETE',
      body: JSON.stringify({ name }),
    });
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.error || 'Не вдалося видалити модель');
    }
    return safeJson(response, {});
  },

  async chatStream(model, messages, onChunk, workspaceId = null, options = {}) {
    const controller = options.signal ? null : new AbortController();
    const signal = options.signal || controller?.signal;

    const response = await this._fetchWithAuth('/ollama/chat/', {
      method: 'POST',
      body: JSON.stringify({
        model,
        messages,
        stream: true,
        workspace_id: workspaceId,
      }),
      signal,
    });

    if (!response.ok) {
      let message = 'Chat stream failed';
      let code = '';
      try {
        const error = await response.json();
        message = error.error || message;
        code = error.code || '';
      } catch (parseErr) {
        console.error('Chat error response is not JSON:', parseErr);
      }
      const err = new Error(message);
      err.code = code;
      throw err;
    }

    await this._consumeSSE(response, onChunk, signal);
    return { abort: () => controller?.abort() };
  },

  pullModelStream(name, onProgress) {
    const controller = new AbortController();

    this._fetchWithAuth('/ollama/models/pull/', {
      method: 'POST',
      body: JSON.stringify({ name }),
      signal: controller.signal,
    }).then(async (response) => {
      if (!response.ok) {
        const error = await safeJson(response, {});
        onProgress({ error: error.error || 'Не вдалося завантажити модель' });
        return;
      }
      await this._consumeSSE(response, onProgress);
    }).catch((err) => {
      console.error('Model pull stream error:', err);
      if (err.message !== 'Unauthorized') {
        onProgress({ error: err.message || 'Не вдалося завантажити модель' });
      }
    });

    return controller;
  },
};

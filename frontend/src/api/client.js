import { safeJson } from '../utils/safeJson.js';
import { consumeSSE } from '../utils/sse.js';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

class ApiClient {
  constructor() {
    this.baseUrl = API_BASE;
  }

  getToken() {
    return localStorage.getItem('access_token');
  }

  setTokens(access, refresh) {
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
  }

  clearTokens() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
  }

  async _fetchWithAuth(path, options = {}, isRetry = false) {
    const headers = {
      ...options.headers,
    };

    const isFormData = options.body instanceof FormData;
    if (!isFormData && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    const token = this.getToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers,
    });

    if (response.status === 401 && !path.includes('/auth/') && !isRetry) {
      const refreshed = await this.refreshToken();
      if (refreshed) {
        return this._fetchWithAuth(path, options, true);
      }
      this.clearTokens();
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }

    return response;
  }

  async _consumeSSE(response, onChunk, signal = null) {
    await consumeSSE(response, onChunk, { signal });
  }

  async request(path, options = {}) {
    return this._fetchWithAuth(path, options);
  }

  async refreshToken() {
    const refresh = localStorage.getItem('refresh_token');
    if (!refresh) return false;

    try {
      const response = await fetch(`${this.baseUrl}/auth/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh }),
      });

      if (!response.ok) return false;

      const data = await response.json();
      localStorage.setItem('access_token', data.access);
      return true;
    } catch {
      return false;
    }
  }

  async getAuthConfig() {
    const response = await fetch(`${this.baseUrl}/auth/config/`);
    if (!response.ok) {
      return { allow_registration: true };
    }
    return response.json();
  }

  async login(username, password) {
    const response = await this.request('/auth/login/', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });

    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.detail || 'Помилка входу');
    }

    const data = await safeJson(response);
    this.setTokens(data.access, data.refresh);
    if (data.user) {
      localStorage.setItem('user', JSON.stringify(data.user));
    }
    return data;
  }

  async register(userData) {
    const response = await this.request('/auth/register/', {
      method: 'POST',
      body: JSON.stringify(userData),
    });

    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(
        error.detail || error.non_field_errors?.[0] || JSON.stringify(error),
      );
    }

    return safeJson(response);
  }

  async getCurrentUser() {
    const response = await this.request('/auth/me/');
    if (!response.ok) throw new Error('Failed to fetch user');
    return response.json();
  }

  async changePassword({ current_password, new_password, new_password_confirm }) {
    const response = await this.request('/auth/me/change-password/', {
      method: 'POST',
      body: JSON.stringify({
        current_password,
        new_password,
        new_password_confirm,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      const message = error.detail
        || error.current_password?.[0]
        || error.new_password?.[0]
        || error.new_password_confirm?.[0]
        || Object.values(error).flat()[0]
        || 'Failed to change password';
      throw new Error(message);
    }

    return response.json();
  }

  async getUsers() {
    const response = await this.request('/auth/users/');
    if (!response.ok) throw new Error('Failed to fetch users');
    return response.json();
  }

  async createUser(userData) {
    const response = await this.request('/auth/users/', {
      method: 'POST',
      body: JSON.stringify(userData),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(JSON.stringify(error));
    }

    return response.json();
  }

  async deleteUser(userId) {
    const response = await this.request(`/auth/users/${userId}/`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(
        error.detail
        || error.non_field_errors?.[0]
        || 'Failed to delete user',
      );
    }
    return true;
  }

  async updateUser(userId, userData) {
    const response = await this.request(`/auth/users/${userId}/`, {
      method: 'PATCH',
      body: JSON.stringify(userData),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(
        error.detail
        || error.non_field_errors?.[0]
        || Object.values(error).flat()[0]
        || 'Failed to update user',
      );
    }

    return response.json();
  }

  async getWorkspaces() {
    const response = await this.request('/workspaces/');
    if (!response.ok) throw new Error('Failed to fetch workspaces');
    return response.json();
  }

  async createWorkspace(data) {
    const response = await this.request('/workspaces/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(
        error.name?.[0]
        || error.detail
        || Object.values(error).flat()[0]
        || 'Failed to create workspace',
      );
    }
    return response.json();
  }

  async updateWorkspace(workspaceId, data) {
    const response = await this.request(`/workspaces/${workspaceId}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(
        error.name?.[0]
        || error.detail
        || Object.values(error).flat()[0]
        || 'Failed to update workspace',
      );
    }
    return response.json();
  }

  async deleteWorkspace(workspaceId) {
    const response = await this.request(`/workspaces/${workspaceId}/`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete workspace');
    return true;
  }

  async getWidgetTokens(workspaceId) {
    const response = await this.request(`/workspaces/${workspaceId}/widget-tokens/`);
    if (!response.ok) throw new Error('Failed to fetch widget tokens');
    return response.json();
  }

  async createWidgetToken(workspaceId, label = '') {
    const response = await this.request(`/workspaces/${workspaceId}/widget-tokens/`, {
      method: 'POST',
      body: JSON.stringify({ label }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to create widget token');
    }
    return response.json();
  }

  async deleteWidgetToken(workspaceId, tokenId) {
    const response = await this.request(
      `/workspaces/${workspaceId}/widget-tokens/${tokenId}/`,
      { method: 'DELETE' },
    );
    if (!response.ok) throw new Error('Failed to delete widget token');
    return true;
  }

  async getWorkspaceDocuments(workspaceId) {
    const response = await this.request(`/workspaces/${workspaceId}/documents/`);
    if (!response.ok) throw new Error('Failed to fetch documents');
    return response.json();
  }

  async uploadWorkspaceDocument(workspaceId, file) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await this._fetchWithAuth(
      `/workspaces/${workspaceId}/documents/`,
      { method: 'POST', body: formData },
    );

    if (!response.ok) {
      const error = await safeJson(response, {});
      const message = error.file?.[0]
        || error.detail
        || error.error
        || 'Failed to upload document';
      throw new Error(message);
    }

    return response.json();
  }

  async deleteWorkspaceDocument(workspaceId, documentId) {
    const response = await this.request(
      `/workspaces/${workspaceId}/documents/${documentId}/`,
      { method: 'DELETE' },
    );
    if (!response.ok) throw new Error('Failed to delete document');
    return true;
  }

  async retryWorkspaceDocument(workspaceId, documentId) {
    const response = await this.request(
      `/workspaces/${workspaceId}/documents/${documentId}/retry/`,
      { method: 'POST' },
    );
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.error || 'Failed to retry document');
    }
    return response.json();
  }

  async getWorkspaceRagStats(workspaceId) {
    const response = await this.request(`/workspaces/${workspaceId}/rag-stats/`);
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.error || error.detail || 'Failed to fetch RAG stats');
    }
    return response.json();
  }

  /** Масовий reindex усіх failed документів workspace. */
  async reindexFailedWorkspaceDocuments(workspaceId) {
    const response = await this.request(`/workspaces/${workspaceId}/rag-stats/`, {
      method: 'POST',
    });
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.error || 'Failed to reindex documents');
    }
    return response.json();
  }

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
      throw new Error(error.error || 'Failed to submit feedback');
    }
    return response.json();
  }

  async getMyWorkspaces() {
    const response = await this.request('/workspaces/my/');
    if (!response.ok) throw new Error('Failed to fetch workspaces');
    return response.json();
  }

  async getChats() {
    const response = await this.request('/chats/');
    if (!response.ok) throw new Error('Failed to fetch chats');
    return response.json();
  }

  async getChat(chatId) {
    const response = await this.request(`/chats/${chatId}/`);
    if (!response.ok) throw new Error('Failed to fetch chat');
    return response.json();
  }

  async createChat(data) {
    const response = await this.request('/chats/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to create chat');
    }
    return response.json();
  }

  async updateChat(chatId, data) {
    const response = await this.request(`/chats/${chatId}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to update chat');
    }
    return response.json();
  }

  async deleteChat(chatId) {
    const response = await this.request(`/chats/${chatId}/`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete chat');
    return true;
  }

  async getOllamaHealth() {
    const response = await this.request('/ollama/health/');
    if (!response.ok) {
      return { connected: false };
    }
    return safeJson(response, { connected: false });
  }

  async getModels() {
    const response = await this.request('/ollama/models/');
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to fetch models');
    }
    return response.json();
  }

  async deleteModel(name) {
    const response = await this.request('/ollama/models/delete/', {
      method: 'DELETE',
      body: JSON.stringify({ name }),
    });
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.error || 'Failed to delete model');
    }
    return safeJson(response, {});
  }

  async chat(model, messages, stream = false, workspaceId = null) {
    const response = await this.request('/ollama/chat/', {
      method: 'POST',
      body: JSON.stringify({
        model,
        messages,
        stream,
        workspace_id: workspaceId,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Chat failed');
    }

    return response.json();
  }

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
      try {
        const error = await response.json();
        message = error.error || message;
      } catch {
        /* ignore */
      }
      throw new Error(message);
    }

    await this._consumeSSE(response, onChunk, signal);
    return { abort: () => controller?.abort() };
  }

  pullModelStream(name, onProgress) {
    const controller = new AbortController();

    this._fetchWithAuth('/ollama/models/pull/', {
      method: 'POST',
      body: JSON.stringify({ name }),
      signal: controller.signal,
    }).then(async (response) => {
      if (!response.ok) {
        let message = 'Failed to pull model';
        try {
          const error = await response.json();
          message = error.error || message;
        } catch {
          /* ignore */
        }
        onProgress({ error: message });
        return;
      }
      await this._consumeSSE(response, onProgress);
    }).catch((err) => {
      if (err.message !== 'Unauthorized') {
        onProgress({ error: err.message || 'Failed to pull model' });
      }
    });

    return controller;
  }

  async getBackups() {
    const response = await this.request('/backups/');
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to fetch backups');
    }
    return response.json();
  }

  async createBackup() {
    const response = await this.request('/backups/', { method: 'POST' });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to create backup');
    }
    return response.json();
  }

  async deleteBackup(filename) {
    const response = await this.request(
      `/backups/${encodeURIComponent(filename)}/`,
      { method: 'DELETE' },
    );
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to delete backup');
    }
    return response.json();
  }

  async downloadBackup(filename) {
    const token = this.getToken();
    const response = await fetch(
      `${this.baseUrl}/backups/${encodeURIComponent(filename)}/download/`,
      { headers: { Authorization: `Bearer ${token}` } },
    );

    if (!response.ok) {
      throw new Error('Failed to download backup');
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    window.URL.revokeObjectURL(url);
  }

  async getWorkspaceChatLogs() {
    const response = await this.request('/chats/logs/');
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.error || error.detail || 'Failed to fetch workspace chats');
    }
    return safeJson(response, []);
  }

  async deleteWorkspaceChatLog(logId) {
    const response = await this.request(`/chats/logs/${logId}/`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.error || error.detail || 'Failed to delete chat log');
    }
    return safeJson(response, {});
  }

  async clearWorkspaceChatLogs() {
    const response = await this.request('/chats/logs/clear/', {
      method: 'DELETE',
    });
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.error || error.detail || 'Failed to clear chat logs');
    }
    return safeJson(response, {});
  }

  async exportWorkspaceChatLogs(format) {
    const token = this.getToken();
    const response = await fetch(
      `${this.baseUrl}/chats/logs/export/?export_format=${encodeURIComponent(format)}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );

    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.error || error.detail || 'Failed to export chat logs');
    }

    const blob = await response.blob();
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match?.[1] || `workspace_chats.${format}`;
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    window.URL.revokeObjectURL(url);
  }
}

export const api = new ApiClient();

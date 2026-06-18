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

  async request(path, options = {}) {
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    const token = this.getToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers,
    });

    if (response.status === 401 && !path.includes('/auth/')) {
      const refreshed = await this.refreshToken();
      if (refreshed) {
        headers.Authorization = `Bearer ${this.getToken()}`;
        return fetch(`${this.baseUrl}${path}`, { ...options, headers });
      }
      this.clearTokens();
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }

    return response;
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

  async login(username, password) {
    const response = await this.request('/auth/login/', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Помилка входу');
    }

    const data = await response.json();
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
      const error = await response.json();
      throw new Error(JSON.stringify(error));
    }

    return response.json();
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
    return response.json();
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
    return response.json();
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

  async chatStream(model, messages, onChunk, workspaceId = null) {
    const token = this.getToken();
    const response = await fetch(`${this.baseUrl}/ollama/chat/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        model,
        messages,
        stream: true,
        workspace_id: workspaceId,
      }),
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

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    let doneReading = false;
    while (!doneReading) {
      const { done, value } = await reader.read();
      doneReading = done;
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            onChunk(data);
          } catch {
            /* skip malformed chunks */
          }
        }
      }
    }
  }

  pullModelStream(name, onProgress) {
    const token = this.getToken();
    const controller = new AbortController();

    fetch(`${this.baseUrl}/ollama/models/pull/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ name }),
      signal: controller.signal,
    }).then(async (response) => {
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      let doneReading = false;
      while (!doneReading) {
        const { done, value } = await reader.read();
        doneReading = done;
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              onProgress(data);
            } catch {
              /* skip malformed chunks */
            }
          }
        }
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
}

export const api = new ApiClient();

import { safeJson } from '../utils/safeJson.js';
import { consumeSSE } from '../utils/sse.js';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

export class BaseApiClient {
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
}

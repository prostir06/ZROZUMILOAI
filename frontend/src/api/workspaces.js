import { safeJson } from '../utils/safeJson.js';

function extractWorkspaceError(error, fallback) {
  return error.name?.[0]
    || error.detail
    || Object.values(error).flat()[0]
    || fallback;
}

export const workspaceApiMethods = {
  async getWorkspaces() {
    const response = await this.request('/workspaces/');
    if (!response.ok) throw new Error('Не вдалося отримати workspace');
    return response.json();
  },

  async createWorkspace(data) {
    const response = await this.request('/workspaces/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(extractWorkspaceError(error, 'Не вдалося створити workspace'));
    }
    return response.json();
  },

  async updateWorkspace(workspaceId, data) {
    const response = await this.request(`/workspaces/${workspaceId}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(extractWorkspaceError(error, 'Не вдалося оновити workspace'));
    }
    return response.json();
  },

  async deleteWorkspace(workspaceId) {
    const response = await this.request(`/workspaces/${workspaceId}/`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Не вдалося видалити workspace');
    return true;
  },

  async getMyWorkspaces() {
    const response = await this.request('/workspaces/my/');
    if (!response.ok) throw new Error('Не вдалося отримати workspace');
    return response.json();
  },

  async getWidgetTokens(workspaceId) {
    const response = await this.request(`/workspaces/${workspaceId}/widget-tokens/`);
    if (!response.ok) throw new Error('Не вдалося отримати widget tokens');
    return response.json();
  },

  async createWidgetToken(workspaceId, label = '', openedxCourseId = '') {
    const response = await this.request(`/workspaces/${workspaceId}/widget-tokens/`, {
      method: 'POST',
      body: JSON.stringify({
        label,
        openedx_course_id: openedxCourseId || '',
      }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || error.error || 'Не вдалося створити widget token');
    }
    return response.json();
  },

  async deleteWidgetToken(workspaceId, tokenId) {
    const response = await this.request(
      `/workspaces/${workspaceId}/widget-tokens/${tokenId}/`,
      { method: 'DELETE' },
    );
    if (!response.ok) throw new Error('Не вдалося видалити widget token');
    return true;
  },

  async getWorkspaceDocuments(workspaceId) {
    const response = await this.request(`/workspaces/${workspaceId}/documents/`);
    if (!response.ok) throw new Error('Не вдалося отримати документи');
    return response.json();
  },

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
        || 'Не вдалося завантажити документ';
      throw new Error(message);
    }

    return response.json();
  },

  async deleteWorkspaceDocument(workspaceId, documentId) {
    const response = await this.request(
      `/workspaces/${workspaceId}/documents/${documentId}/`,
      { method: 'DELETE' },
    );
    if (!response.ok) throw new Error('Не вдалося видалити документ');
    return true;
  },

  async retryWorkspaceDocument(workspaceId, documentId) {
    const response = await this.request(
      `/workspaces/${workspaceId}/documents/${documentId}/retry/`,
      { method: 'POST' },
    );
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.error || 'Не вдалося повторити індексацію');
    }
    return response.json();
  },

  async getWorkspaceRagStats(workspaceId) {
    const response = await this.request(`/workspaces/${workspaceId}/rag-stats/`);
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.error || error.detail || 'Не вдалося отримати RAG-статистику');
    }
    return response.json();
  },

  /** Масовий reindex усіх failed документів workspace. */
  async reindexFailedWorkspaceDocuments(workspaceId) {
    const response = await this.request(`/workspaces/${workspaceId}/rag-stats/`, {
      method: 'POST',
    });
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.error || 'Не вдалося переіндексувати документи');
    }
    return response.json();
  },

  async getWorkspaceAnalytics(workspaceId, { range = '30d' } = {}) {
    const response = await this.request(
      `/workspaces/${workspaceId}/analytics/?range=${encodeURIComponent(range)}`,
    );
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.detail || error.error || 'Не вдалося отримати аналітику');
    }
    return response.json();
  },

  async resolveKnowledgeGap(workspaceId, logId, resolved = true) {
    const response = await this.request(
      `/workspaces/${workspaceId}/analytics/gaps/${logId}/resolve/`,
      {
        method: 'PATCH',
        body: JSON.stringify({ resolved }),
      },
    );
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.detail || error.error || 'Не вдалося оновити статус прогалини');
    }
    return response.json();
  },

  async exportWorkspaceAnalyticsCsv(workspaceId, { range = '30d' } = {}) {
    const response = await this.request(
      `/workspaces/${workspaceId}/analytics/export/?range=${encodeURIComponent(range)}`,
    );
    if (!response.ok) {
      const error = await safeJson(response, {});
      throw new Error(error.detail || error.error || 'Не вдалося експортувати аналітику');
    }

    const blob = await response.blob();
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match?.[1] || `workspace_${workspaceId}_analytics_${range}.csv`;
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    window.URL.revokeObjectURL(url);
  },
};

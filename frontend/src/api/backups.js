export const backupApiMethods = {
  async getBackups() {
    const response = await this.request('/backups/');
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Не вдалося отримати резервні копії');
    }
    return response.json();
  },

  async createBackup() {
    const response = await this.request('/backups/', { method: 'POST' });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Не вдалося створити резервну копію');
    }
    return response.json();
  },

  async deleteBackup(filename) {
    const response = await this.request(
      `/backups/${encodeURIComponent(filename)}/`,
      { method: 'DELETE' },
    );
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Не вдалося видалити резервну копію');
    }
    return response.json();
  },

  async downloadBackup(filename) {
    const token = this.getToken();
    const response = await fetch(
      `${this.baseUrl}/backups/${encodeURIComponent(filename)}/download/`,
      { headers: { Authorization: `Bearer ${token}` } },
    );

    if (!response.ok) {
      throw new Error('Не вдалося завантажити резервну копію');
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    window.URL.revokeObjectURL(url);
  },
};

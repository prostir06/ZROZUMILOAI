import { buildAuthHeader, isIso88591, safeJson } from './utils.js';

/** HTTP-запит до backend API. */
export async function apiRequest(config, path, options = {}) {
  try {
    const authHeader = buildAuthHeader(config);
    const headers = {
      'Content-Type': 'application/json',
      ...(authHeader ? { Authorization: authHeader } : {}),
      ...options.headers,
    };
    for (const [key, value] of Object.entries(headers)) {
      if (!isIso88591(key) || !isIso88591(value)) {
        delete headers[key];
      }
    }
    const response = await fetch(`${config.apiUrl}${path}`, {
      ...options,
      headers,
    });
    return response;
  } catch (error) {
    throw new Error(error.message || 'Помилка мережі');
  }
}

/** Завантажити workspace і модель за токеном або API-ключем. */
export async function fetchWorkspaceConfig(config) {
  if (!config) {
    return { workspace: null, model: '', initError: 'Конфігурація відсутня' };
  }

  if (config.widgetToken) {
    if (!isIso88591(config.widgetToken)) {
      return {
        workspace: null,
        model: '',
        initError: 'Некоректний токен: токен містить неприпустимі не-ASCII символи. Будь ласка, замініть кириличний плейсхолдер у data-widget-token на дійсний токен із панелі Workspaces.',
      };
    }
    const response = await apiRequest(config, '/widget/config/');
    if (!response.ok) {
      const error = await safeJson(response);
      return {
        workspace: null,
        model: '',
        initError: error.error || error.detail || `Помилка конфігурації (${response.status})`,
      };
    }
    const data = await safeJson(response);
    const workspace = data.workspace || null;
    if (workspace) {
      workspace.greeting = data.greeting || '';
      workspace.faq_questions = data.faq_questions || [];
    }
    const model = data.model || workspace?.model_names?.[0] || '';
    const initError = !workspace ? 'Widget token недійсний або workspace недоступний.' : '';
    return { workspace, model, initError };
  }

  if (config.apiKey && !isIso88591(config.apiKey)) {
    return {
      workspace: null,
      model: '',
      initError: 'Некоректний API-ключ: містить неприпустимі не-ASCII символи.',
    };
  }

  const response = await apiRequest(config, '/workspaces/my/');
  if (!response.ok) {
    const error = await safeJson(response);
    return {
      workspace: null,
      model: '',
      initError: error.error || error.detail || `Помилка завантаження workspace (${response.status})`,
    };
  }

  const workspaces = await safeJson(response, []);
  const workspace = Array.isArray(workspaces)
    ? (workspaces.find((item) => item.name === config.workspaceName) || null)
    : null;
  const model = workspace?.model_names?.[0] || '';
  const initError = !workspace ? `Workspace «${config.workspaceName}» не знайдено.` : '';
  return { workspace, model, initError };
}

/** SSE-стрімінг відповіді чату. */
export async function sendChatMessageStream({
  config,
  workspace,
  model,
  messages,
  onChunk,
}) {
  if (!workspace?.id && !config?.widgetToken) {
    throw new Error('Workspace не завантажено');
  }

  const chatPath = config.widgetToken ? '/widget/chat/' : '/ollama/chat/';
  const body = config.widgetToken
    ? { stream: true, messages }
    : {
      model,
      workspace_id: workspace.id,
      stream: true,
      messages,
    };

  if (config.openedxCourseId) {
    body.openedx_course_id = config.openedxCourseId;
  }

  const response = await apiRequest(config, chatPath, {
    method: 'POST',
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await safeJson(response);
    const err = new Error(error.error || error.detail || 'Помилка чату');
    err.code = error.code || '';
    throw err;
  }

  if (!response.body) {
    throw new Error('Порожня відповідь сервера');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  let doneReading = false;
  while (!doneReading) {
    const { done, value } = await reader.read();
    doneReading = done;
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) {
        continue;
      }
      try {
        const data = JSON.parse(line.slice(6));
        onChunk(data);
      } catch (err) {
        console.warn('[ZrozumiloAI Embed] Invalid SSE JSON chunk:', err);
      }
    }
  }
}

/** Надіслати feedback з embed через Widget-Token. */
export async function sendFeedback({ config, logId, payload }) {
  return apiRequest(config, `/widget/logs/${logId}/feedback/`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

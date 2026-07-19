/**
 * ZrozumiloAI — вбудовуваний віджет чату підтримки.
 *
 * data-атрибути тега <script>:
 *   data-widget-token   — токен віджета (або пара api-key + workspace)
 *   data-api-key        — API-ключ ZrozumiloAI
 *   data-workspace      — ім'я workspace (разом з api-key)
 *   data-api-url        — базовий URL API (за замовч. origin скрипта + /api)
 *   data-embed-url      — URL embed.html (за замовч. origin + /embed.html)
 *   data-title          — заголовок панелі чату
 *   data-color          — колір кнопки (hex, напр. #0D9E96)
 *   data-position       — left | right
 *   data-z-index        — z-index панелі та кнопки
 *   data-openedx-course-id — фільтр курсу Open edX для Meilisearch
 */
(function initZrozumiloWidget() {
  /** Дозволити лише безпечний hex-колір для CSS. */
  function sanitizeColor(color) {
    const value = String(color || '').trim();
    if (/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(value)) {
      return value;
    }
    return '#0D9E96';
  }

  /** Прибрати небезпечні символи з заголовка iframe. */
  function sanitizeTitle(title) {
    const value = String(title || 'Підтримка').trim();
    const cleaned = value.replace(/[<>"']/g, '');
    return cleaned.slice(0, 80) || 'Підтримка';
  }

  /** Монтування віджета після готовності DOM. */
  function mountWidget() {
    const script = document.currentScript;
    if (!script) {
      console.error('[ZrozumiloAI] Не вдалося знайти тег script');
      return;
    }

    let scriptOrigin;
    try {
      scriptOrigin = new URL(script.src, window.location.href).origin;
    } catch (error) {
      console.error('[ZrozumiloAI] Некоректний src скрипта:', error);
      return;
    }

    const widgetToken = script.dataset.widgetToken
      || script.getAttribute('data-widget-token');
    const apiKey = script.dataset.apiKey || script.getAttribute('data-api-key');
    const workspaceName = script.dataset.workspace
      || script.getAttribute('data-workspace');

    if (!widgetToken && !(apiKey && workspaceName)) {
      console.error(
        '[ZrozumiloAI] Потрібен data-widget-token або data-api-key + data-workspace',
      );
      return;
    }

    const parsedZIndex = Number(script.dataset.zIndex);
    const zIndex = Number.isFinite(parsedZIndex) ? parsedZIndex : 999999;

    const config = {
      apiUrl: script.dataset.apiUrl || `${scriptOrigin}/api`,
      embedUrl: script.dataset.embedUrl || `${scriptOrigin}/embed.html`,
      widgetToken: widgetToken || null,
      apiKey: apiKey || null,
      workspaceName: workspaceName ? String(workspaceName).trim() : '',
      title: sanitizeTitle(script.dataset.title),
      color: sanitizeColor(script.dataset.color),
      position: script.dataset.position === 'left' ? 'left' : 'right',
      zIndex,
      openedxCourseId: (
        script.dataset.openedxCourseId
        || script.getAttribute('data-openedx-course-id')
        || ''
      ).trim(),
    };

    if (document.getElementById('zrozumiloai-widget-root')) {
      console.warn('[ZrozumiloAI] Віджет уже ініціалізовано на цій сторінці');
      return;
    }

    const root = document.createElement('div');
    root.id = 'zrozumiloai-widget-root';
    root.setAttribute('aria-live', 'polite');
    document.body.appendChild(root);

    const shadow = root.attachShadow({ mode: 'open' });
    const side = config.position === 'left' ? 'left' : 'right';
    const safeTitle = sanitizeTitle(config.title);

    shadow.innerHTML = `
    <style>
      :host, * { box-sizing: border-box; font-family: Inter, system-ui, sans-serif; }
      .launcher {
        position: fixed;
        bottom: 24px;
        ${side}: 24px;
        z-index: ${config.zIndex};
        width: 56px;
        height: 56px;
        border: none;
        border-radius: 50%;
        background: ${config.color};
        color: #fff;
        cursor: pointer;
        box-shadow: 0 4px 20px rgba(0,0,0,0.18);
        display: flex;
        align-items: center;
        justify-content: center;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
      }
      .launcher:hover { transform: scale(1.05); box-shadow: 0 6px 24px rgba(0,0,0,0.22); }
      .launcher:focus-visible { outline: 2px solid #fff; outline-offset: 2px; }
      .launcher svg { width: 26px; height: 26px; fill: currentColor; }
      .panel {
        position: fixed;
        bottom: 92px;
        ${side}: 24px;
        z-index: ${config.zIndex};
        width: min(400px, calc(100vw - 32px));
        height: min(560px, calc(100vh - 120px));
        border: none;
        border-radius: 16px;
        box-shadow: 0 12px 40px rgba(0,0,0,0.18);
        background: #fff;
        display: none;
        overflow: hidden;
      }
      .panel--open { display: block; }
      @media (max-width: 480px) {
        .panel {
          bottom: 0;
          ${side}: 0;
          width: 100vw;
          height: 100vh;
          border-radius: 0;
        }
        .launcher { bottom: 16px; ${side}: 16px; }
      }
    </style>
    <button type="button" class="launcher" aria-label="Відкрити чат підтримки" aria-expanded="false">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.2L4 17.2V4h16v12z"/></svg>
    </button>
    <iframe
      class="panel"
      title="${safeTitle}"
      allow="clipboard-write"
      sandbox="allow-scripts allow-same-origin allow-forms"
    ></iframe>
  `;

    const launcher = shadow.querySelector('.launcher');
    const panel = shadow.querySelector('.panel');
    let isOpen = false;
    let loadTimeoutId = null;

    function sendConfig() {
      if (!panel.contentWindow) {
        return;
      }
      try {
        panel.contentWindow.postMessage(
          { type: 'zrozumiloai-config', config },
          scriptOrigin,
        );
      } catch (error) {
        console.error('[ZrozumiloAI] Не вдалося надіслати конфіг:', error);
      }
    }

    function clearLoadTimeout() {
      if (loadTimeoutId) {
        clearTimeout(loadTimeoutId);
        loadTimeoutId = null;
      }
    }

    panel.addEventListener('load', () => {
      clearLoadTimeout();
    });

    function buildEmbedUrl() {
      // Стабільний URL без Date.now() — дозволяє кешувати embed assets (P0).
      try {
        return new URL(config.embedUrl, scriptOrigin).toString();
      } catch (error) {
        console.error('[ZrozumiloAI] Некоректний embedUrl:', error);
        return String(config.embedUrl || '');
      }
    }

    function setOpen(open) {
      isOpen = open;
      panel.classList.toggle('panel--open', open);
      launcher.setAttribute('aria-expanded', open ? 'true' : 'false');
      launcher.innerHTML = open
        ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>'
        : '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.2L4 17.2V4h16v12z"/></svg>';
      if (open) {
        clearLoadTimeout();
        panel.src = buildEmbedUrl();
        loadTimeoutId = setTimeout(() => {
          if (!panel.contentWindow) {
            console.error('[ZrozumiloAI] Таймаут завантаження iframe чату');
          }
        }, 15000);
      } else {
        clearLoadTimeout();
      }
    }

    launcher.addEventListener('click', () => setOpen(!isOpen));

    window.addEventListener('message', (event) => {
      if (event.origin !== scriptOrigin) {
        return;
      }
      if (event.data?.type === 'zrozumiloai-close') {
        setOpen(false);
      }
      if (event.data?.type === 'zrozumiloai-ready') {
        sendConfig();
      }
    });
  }

  if (document.body) {
    mountWidget();
  } else {
    document.addEventListener('DOMContentLoaded', mountWidget);
  }
})();

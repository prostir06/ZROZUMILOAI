/**
 * Приклад FPF footer slot для Learning MFE (Tutor 21+).
 *
 * НЕ підключається автоматично — скопіюйте в свій frontend plugin
 * і зареєструйте slot згідно документації Open edX Frontend Plugin Framework.
 *
 * Env (build-time):
 *   process.env.ZROZUMILOAI_WIDGET_JS_URL
 *   process.env.ZROZUMILOAI_WIDGET_TOKEN
 */
import { useEffect } from 'react';

const WIDGET_JS_URL = process.env.ZROZUMILOAI_WIDGET_JS_URL || '';
const WIDGET_TOKEN = process.env.ZROZUMILOAI_WIDGET_TOKEN || '';

export default function ZrozumiloFooterSlot() {
  useEffect(() => {
    if (!WIDGET_JS_URL || !WIDGET_TOKEN) {
      return undefined;
    }
    if (document.querySelector('script[data-zrozumilo-widget="1"]')) {
      return undefined;
    }
    const script = document.createElement('script');
    script.src = WIDGET_JS_URL;
    script.async = true;
    script.dataset.zrozumiloWidget = '1';
    script.dataset.widgetToken = WIDGET_TOKEN;
    script.dataset.title = 'Підтримка';
    document.body.appendChild(script);
    return () => {
      script.remove();
    };
  }, []);

  return null;
}

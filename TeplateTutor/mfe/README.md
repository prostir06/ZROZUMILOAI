# Open edX Learning MFE — footer slot для віджета ZrozumiloAI

Legacy LMS тема (`zrozumilo/lms`) **не** покриває Learning MFE (Tutor 21+).
Для MFE потрібен frontend plugin з `org.openedx.frontend.layout.footer` (FPF).

## Швидкий шлях (рекомендовано)

1. Додайте посилання «Підтримка» у footer MFE на ваш ZrozumiloAI URL
   (наприклад `https://chat.example.com`), або
2. Підключіть `widget.js` через custom frontend plugin (див. нижче).

## Мінімальний frontend plugin

Каталог-приклад: [`footer-plugin.example.jsx`](footer-plugin.example.jsx).

Ідея: у slot `footer` (або `footer_slot`) відрендерити:

```jsx
<script src={WIDGET_JS_URL} data-widget-token={TOKEN} data-title="Підтримка" />
```

Кроки (загальна схема для `@edx/frontend-component-footer` / FPF):

1. Створіть npm-пакет plugin з `env.config.js` / `module.config.js` за документацією Tutor MFE.
2. Зареєструйте slot для footer.
3. Зберіть Learning MFE з plugin і задеплойте через Tutor (`tutor config` + rebuild MFE image).

Змінні:

| Env | Приклад |
|-----|---------|
| `ZROZUMILOAI_WIDGET_JS_URL` | `https://chat.example.com/widget.js` |
| `ZROZUMILOAI_WIDGET_TOKEN` | `wt_...` (з адмінки Workspaces) |

## Перевірка

- Legacy LMS: віджет у `body-extra.html` після `settheme zrozumilo`.
- Learning MFE: footer slot містить script tag / кнопку підтримки.
- CSP LMS/MFE дозволяє `script-src` / `connect-src` origin чату (див. `tutorzrozumilo/plugin.py`).

## Обмеження

- Цей репозиторій не шипить готовий published npm MFE plugin — лише приклад і docs.
- CMS/Studio theme не входить у scope (див. основний README).

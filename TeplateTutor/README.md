# TeplateTutor — кастомна тема Open edX (Tutor)

Тема **zrozumilo** додає віджет чату ZrozumiloAI на legacy-сторінки LMS (після footer, перед `</body>`).

## Структура

```
TeplateTutor/
  zrozumilo/
    theme.conf
    lms/
      templates/
        body-extra.html                        ← partial з main.html (рекомендовано)
        zrozumilo-widget.html                  ← скрипт віджета
        snippets/footer_extra-zrozumilo.html   ← фрагмент для override main.html
```

Open edX у базовому `lms/templates/main.html` автоматично підключає partial теми **перед `</body>`** (після footer):

```html
<%static:optional_include_mako file="body-extra.html" is_theming_enabled="True" />
```

Файл `body-extra.html` — рекомендований спосіб. Якщо ви повністю перевизначаєте `main.html`, додайте у блок `footer_extra`:

```html
<%block name="footer_extra">
  <%include file="snippets/footer_extra-zrozumilo.html"/>
</%block>
```

## Встановлення (Tutor 21+)

> У Tutor 21 **немає** команд `tutor themes create` / `tutor themes enable`. Тему копіюють у каталог вручну, потім увімкнюють через `settheme`.

1. Активуйте venv і перейдіть у репозиторій:

```bash
source ~/tutor-env/bin/activate
cd ~/ZROZUMILOAI   # шлях до репо
```

2. Скопіюйте файли теми:

```bash
THEME_DIR="$(tutor config printroot)/env/build/openedx/themes/zrozumilo"
mkdir -p "$THEME_DIR"
cp -r TeplateTutor/zrozumilo/lms "$THEME_DIR/"
cp TeplateTutor/zrozumilo/theme.conf "$THEME_DIR/"
```

Або: `chmod +x TeplateTutor/install.sh && ./TeplateTutor/install.sh`

3. Увімкніть тему та налаштуйте віджет:

```bash
tutor local do settheme zrozumilo
tutor config save --set ZROZUMILOAI_WIDGET_JS_URL=https://chat.example.com/widget.js
tutor config save --set ZROZUMILOAI_WIDGET_TOKEN=wt_ВАШ_TOKEN
```

Для dev-середовища замість `local` використовуйте `tutor dev do settheme zrozumilo`.

4. Перезберіть і перезапустіть:

```bash
tutor images build openedx
tutor local restart
```

## Tutor plugin (рекомендовано)

Окрім теми, у каталозі є **Tutor plugin** `tutor-contrib-zrozumilo`:

```bash
pip install -e ./TeplateTutor
tutor plugins enable zrozumilo
tutor config save \
  --set ZROZUMILOAI_WIDGET_JS_URL=https://chat.example.com/widget.js \
  --set ZROZUMILOAI_WIDGET_TOKEN=wt_ВАШ_TOKEN
tutor config save   # згенерує ENV_PATCH у openedx-lms-common-settings
```

Тема все одно потрібна (віджет у `body-extra.html`). Plugin лише прокидає Django settings.

На сторінках курсу шаблон передає `data-openedx-course-id` автоматично (якщо в контексті є `course`).

## Налаштування віджета

Відредагуйте `zrozumilo/lms/templates/zrozumilo-widget.html` або задайте змінні через Tutor plugin / `tutor-settings.patch.example`.

| Параметр | Опис |
|----------|------|
| `ZROZUMILOAI_WIDGET_JS_URL` | URL `widget.js` (HTTPS на продакшені) |
| `ZROZUMILOAI_WIDGET_TOKEN` | Token з адмінки ZrozumiloAI → Workspaces |
| `ZROZUMILOAI_WIDGET_TITLE` | Заголовок віджета (за замовч. «Підтримка») |
| `ZROZUMILOAI_WIDGET_COLOR` | Колір `#0D9E96` |

Token створюється: **Workspaces → Редагувати → «Створити token»**. Опційно задайте `openedx_course_id` на токені для course-scoped Meili.

## CSP і HTTPS

Додайте домен ZrozumiloAI до CSP LMS (`script-src`, `frame-src`, `connect-src`) і `CORS_ALLOWED_ORIGINS` на стороні ZrozumiloAI. Приклад patch — `tutor-settings.patch.example`. Деталі — у [README.md](../README.md#як-додати-віджет-чату-до-open-edx).

## MFE (Learning, Dashboard тощо)

`body-extra.html` працює лише на **legacy LMS**-сторінках. Для MFE потрібен окремий Frontend Plugin Framework (слот `footer_slot`). Див. основний README про Open edX.

## CMS (Studio)

Для Studio скопіюйте `lms/templates/zrozumilo-widget.html` у `cms/templates/body-extra.html` за потреби.

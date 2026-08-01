#!/usr/bin/env bash
# Встановлює тему zrozumilo + Tutor plugin у середовище Tutor.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THEME_SRC="${SCRIPT_DIR}/zrozumilo"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if ! command -v tutor >/dev/null 2>&1; then
  echo "Помилка: tutor не знайдено в PATH" >&2
  exit 1
fi

ROOT="$(tutor config printroot)"
THEME_DIR="${ROOT}/env/build/openedx/themes/zrozumilo"

mkdir -p "${THEME_DIR}"
cp -r "${THEME_SRC}/lms" "${THEME_DIR}/"
cp "${THEME_SRC}/theme.conf" "${THEME_DIR}/"

echo "Тему скопійовано в: ${THEME_DIR}"

# Встановити / оновити Tutor plugin (settings + CSP).
if command -v pip >/dev/null 2>&1; then
  pip install -e "${SCRIPT_DIR}"
  echo "Plugin встановлено: pip install -e ${SCRIPT_DIR}"
  echo "Увімкніть: tutor plugins enable zrozumilo && tutor config save"
else
  echo "Попередження: pip не знайдено — встановіть plugin вручну: pip install -e ${SCRIPT_DIR}" >&2
fi

echo "Далі (legacy LMS theme):"
echo "  tutor local do settheme zrozumilo"
echo "  tutor config save --set ZROZUMILOAI_WIDGET_JS_URL=https://chat.example.com/widget.js"
echo "  tutor config save --set ZROZUMILOAI_WIDGET_TOKEN=wt_ВАШ_TOKEN"
echo "  tutor images build openedx && tutor local restart"
echo ""
echo "Learning MFE (Tutor 21+): див. TeplateTutor/mfe/README.md"
echo "Repo root: ${REPO_ROOT}"

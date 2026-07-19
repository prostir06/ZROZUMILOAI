#!/usr/bin/env bash
# Копіює тему zrozumilo у каталог Tutor Open edX themes.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THEME_SRC="${SCRIPT_DIR}/zrozumilo"

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
echo "Далі:"
echo "  tutor local do settheme zrozumilo"
echo "  tutor config save --set ZROZUMILOAI_WIDGET_JS_URL=https://chat.example.com/widget.js"
echo "  tutor config save --set ZROZUMILOAI_WIDGET_TOKEN=wt_ВАШ_TOKEN"
echo "  tutor images build openedx && tutor local restart"

"""Tutor plugin: Open edX settings + CSP для віджета ZrozumiloAI."""
from tutor import hooks

config = {
    'defaults': {
        'ZROZUMILOAI_WIDGET_JS_URL': 'https://chat.example.com/widget.js',
        'ZROZUMILOAI_WIDGET_TOKEN': 'wt_REPLACE_ME',
        'ZROZUMILOAI_WIDGET_TITLE': 'Підтримка',
        'ZROZUMILOAI_WIDGET_COLOR': '#0D9E96',
        # Origin віджета для CSP (без path), напр. https://chat.example.com
        'ZROZUMILOAI_WIDGET_ORIGIN': 'https://chat.example.com',
    },
}

hooks.Filters.ENV_PATCH.add_item(
    (
        'openedx-lms-common-settings',
        """
################# ZrozumiloAI widget #################
ZROZUMILOAI_WIDGET_JS_URL = "{{ ZROZUMILOAI_WIDGET_JS_URL }}"
ZROZUMILOAI_WIDGET_TOKEN = "{{ ZROZUMILOAI_WIDGET_TOKEN }}"
ZROZUMILOAI_WIDGET_TITLE = "{{ ZROZUMILOAI_WIDGET_TITLE }}"
ZROZUMILOAI_WIDGET_COLOR = "{{ ZROZUMILOAI_WIDGET_COLOR }}"

# CSP: дозволити script/frame/connect до origin віджета.
# Працює з django-csp / Open edX CSP settings (списки або tuples).
_ZROZUMILO_ORIGIN = "{{ ZROZUMILOAI_WIDGET_ORIGIN }}"
try:
    CSP_SCRIPT_SRC = tuple(CSP_SCRIPT_SRC) + (_ZROZUMILO_ORIGIN,)
except NameError:
    CSP_SCRIPT_SRC = ("'self'", _ZROZUMILO_ORIGIN)
try:
    CSP_FRAME_SRC = tuple(CSP_FRAME_SRC) + (_ZROZUMILO_ORIGIN,)
except NameError:
    CSP_FRAME_SRC = ("'self'", _ZROZUMILO_ORIGIN)
try:
    CSP_CONNECT_SRC = tuple(CSP_CONNECT_SRC) + (_ZROZUMILO_ORIGIN,)
except NameError:
    CSP_CONNECT_SRC = ("'self'", _ZROZUMILO_ORIGIN)
""",
    ),
)

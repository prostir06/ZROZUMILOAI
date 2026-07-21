"""Tutor plugin: Open edX settings для віджета ZrozumiloAI."""
from tutor import hooks

config = {
    'defaults': {
        'ZROZUMILOAI_WIDGET_JS_URL': 'https://chat.example.com/widget.js',
        'ZROZUMILOAI_WIDGET_TOKEN': 'wt_REPLACE_ME',
        'ZROZUMILOAI_WIDGET_TITLE': 'Підтримка',
        'ZROZUMILOAI_WIDGET_COLOR': '#0D9E96',
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
""",
    ),
)

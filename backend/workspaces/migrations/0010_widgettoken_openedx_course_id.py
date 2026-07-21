"""Widget token: optional Open edX course id."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspaces', '0009_workspace_api_keys_textfield'),
    ]

    operations = [
        migrations.AddField(
            model_name='widgettoken',
            name='openedx_course_id',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Опційний фільтр course-v1:... для Meilisearch у віджеті',
                max_length=255,
            ),
        ),
    ]

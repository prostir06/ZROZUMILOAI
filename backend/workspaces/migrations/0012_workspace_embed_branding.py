# Generated manually for embed branding fields.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspaces', '0011_alter_meilisearch_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='workspace',
            name='embed_greeting',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Привітання embed-віджета (порожнє = дефолт)',
                max_length=500,
            ),
        ),
        migrations.AddField(
            model_name='workspace',
            name='embed_faq_questions',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Список рядків FAQ для швидких кнопок embed',
            ),
        ),
    ]

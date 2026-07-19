from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspaces', '0007_workspace_llm_provider'),
    ]

    operations = [
        migrations.AddField(
            model_name='workspace',
            name='gemini_api_key',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]

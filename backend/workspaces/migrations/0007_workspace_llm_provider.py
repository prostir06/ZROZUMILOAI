from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspaces', '0006_workspace_meilisearch'),
    ]

    operations = [
        migrations.AddField(
            model_name='workspace',
            name='llm_provider',
            field=models.CharField(
                choices=[('ollama', 'Ollama'), ('gemini', 'Google Gemini')],
                default='ollama',
                max_length=20,
            ),
        ),
    ]

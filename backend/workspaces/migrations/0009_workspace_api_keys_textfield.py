"""Міграція: API keys → TextField (Fernet ciphertext може бути >255)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspaces', '0008_workspace_gemini_api_key'),
    ]

    operations = [
        migrations.AlterField(
            model_name='workspace',
            name='gemini_api_key',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='workspace',
            name='meilisearch_api_key',
            field=models.TextField(blank=True, default=''),
        ),
    ]

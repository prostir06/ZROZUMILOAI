from django.db import migrations, models

from workspaces.llm_cleanup import rewrite_llm_fields


def forwards(apps, schema_editor):
    Workspace = apps.get_model('workspaces', 'Workspace')
    for workspace in Workspace.objects.all().iterator():
        provider, names = rewrite_llm_fields(
            workspace.llm_provider,
            workspace.model_names,
        )
        if provider != workspace.llm_provider or list(names) != list(workspace.model_names or []):
            workspace.llm_provider = provider
            workspace.model_names = names
            workspace.save(update_fields=['llm_provider', 'model_names'])


class Migration(migrations.Migration):
    dependencies = [
        ('workspaces', '0013_documentchunk_hnsw_index'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='workspace',
            name='gemini_api_key',
        ),
        migrations.AlterField(
            model_name='workspace',
            name='llm_provider',
            field=models.CharField(
                choices=[('ollama', 'Ollama')],
                default='ollama',
                max_length=20,
            ),
        ),
    ]

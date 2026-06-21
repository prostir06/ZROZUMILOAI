import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspaces', '0005_documentchunk_pgvector'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('chats', '0002_chat_workspace'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkspaceChatLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sent_by', models.CharField(default='unknown user', max_length=150)),
                ('prompt', models.TextField()),
                ('response', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'user',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='workspace_chat_logs',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'workspace',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='chat_logs',
                        to='workspaces.workspace',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Workspace chat log',
                'verbose_name_plural': 'Workspace chat logs',
                'ordering': ('-created_at',),
            },
        ),
    ]

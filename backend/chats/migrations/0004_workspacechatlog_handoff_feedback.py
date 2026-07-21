"""Handoff and feedback fields on WorkspaceChatLog."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0003_workspacechatlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='workspacechatlog',
            name='needs_handoff',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='workspacechatlog',
            name='feedback',
            field=models.CharField(
                blank=True,
                default='',
                help_text='up | down | порожньо',
                max_length=16,
            ),
        ),
    ]

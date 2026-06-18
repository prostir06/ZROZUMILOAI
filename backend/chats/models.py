"""Saved chat sessions."""
from django.conf import settings
from django.db import models


class Chat(models.Model):
    """Persisted chat conversation for a user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chats',
    )
    workspace = models.ForeignKey(
        'workspaces.Workspace',
        on_delete=models.SET_NULL,
        related_name='chats',
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200, default='Новий чат')
    model = models.CharField(max_length=120, blank=True, default='')
    messages = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-updated_at',)
        verbose_name = 'Чат'
        verbose_name_plural = 'Чати'

    def __str__(self):
        return f'{self.title} ({self.user.username})'

"""Workspace models."""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Workspace(models.Model):
    """Named workspace with assigned models and users."""

    name = models.CharField(max_length=200, unique=True)
    system_prompt = models.TextField(blank=True, default='')
    temperature = models.FloatField(
        default=0.7,
        validators=[MinValueValidator(0.0), MaxValueValidator(2.0)],
    )
    model_names = models.JSONField(default=list, blank=True)
    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='workspaces',
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)
        verbose_name = 'Workspace'
        verbose_name_plural = 'Workspaces'

    def __str__(self):
        return self.name

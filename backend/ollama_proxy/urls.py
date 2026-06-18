"""URL routes for Ollama proxy."""
from django.urls import path

from .views import (
  ChatView,
  ModelDeleteView,
  ModelListView,
  ModelPullView,
  OllamaHealthView,
)

urlpatterns = [
  path('health/', OllamaHealthView.as_view(), name='ollama_health'),
  path('models/', ModelListView.as_view(), name='ollama_models'),
  path('models/pull/', ModelPullView.as_view(), name='ollama_pull'),
  path('models/delete/', ModelDeleteView.as_view(), name='ollama_delete'),
  path('chat/', ChatView.as_view(), name='ollama_chat'),
]

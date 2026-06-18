"""URL routes for chats app."""
from django.urls import path

from .views import ChatDetailView, ChatListCreateView

urlpatterns = [
    path('', ChatListCreateView.as_view(), name='chat_list_create'),
    path('<int:chat_id>/', ChatDetailView.as_view(), name='chat_detail'),
]

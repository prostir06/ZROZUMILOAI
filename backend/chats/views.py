"""API views for saved chats."""
from rest_framework import generics, permissions

from .models import Chat
from .serializers import ChatListSerializer, ChatSerializer


class ChatListCreateView(generics.ListCreateAPIView):
    """List or create chats for the current user."""

    permission_classes = (permissions.IsAuthenticated,)

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ChatListSerializer
        return ChatSerializer

    def get_queryset(self):
        queryset = Chat.objects.filter(user=self.request.user)
        if not self.request.user.is_staff:
            workspace_ids = self.request.user.workspaces.values_list('id', flat=True)
            queryset = queryset.filter(workspace_id__in=workspace_ids)
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ChatDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update or delete a chat."""

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ChatSerializer
    lookup_url_kwarg = 'chat_id'

    def get_queryset(self):
        queryset = Chat.objects.filter(user=self.request.user)
        if not self.request.user.is_staff:
            workspace_ids = self.request.user.workspaces.values_list('id', flat=True)
            queryset = queryset.filter(workspace_id__in=workspace_ids)
        return queryset

"""Serializers for saved chats."""
from rest_framework import serializers

from workspaces.services import validate_user_chat_workspace

from .models import Chat, WorkspaceChatLog


class ChatListSerializer(serializers.ModelSerializer):
    """Short chat info for sidebar."""

    class Meta:
        model = Chat
        fields = ('id', 'title', 'model', 'workspace', 'updated_at')
        read_only_fields = fields


class ChatSerializer(serializers.ModelSerializer):
    """Full chat with messages."""

    class Meta:
        model = Chat
        fields = (
            'id',
            'title',
            'model',
            'workspace',
            'messages',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate_messages(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('messages має бути списком')
        for item in value:
            if not isinstance(item, dict):
                raise serializers.ValidationError('Некоректне повідомлення')
            if item.get('role') not in ('user', 'assistant'):
                raise serializers.ValidationError('Некоректна роль повідомлення')
            if not isinstance(item.get('content'), str):
                raise serializers.ValidationError('Некоректний вміст повідомлення')
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        if not request or request.user.is_staff:
            return attrs

        workspace = attrs.get(
            'workspace',
            self.instance.workspace if self.instance else None,
        )
        model = attrs.get(
            'model',
            self.instance.model if self.instance else '',
        )
        validate_user_chat_workspace(request.user, workspace, model)
        return attrs


class WorkspaceChatLogSerializer(serializers.ModelSerializer):
    """Recorded workspace chat exchange for admin dashboard."""

    workspace = serializers.CharField(source='workspace.name', read_only=True)
    sent_at = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = WorkspaceChatLog
        fields = (
            'id',
            'sent_by',
            'workspace',
            'prompt',
            'response',
            'needs_handoff',
            'feedback',
            'sent_at',
        )
        read_only_fields = fields

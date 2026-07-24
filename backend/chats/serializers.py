"""Serializers for saved chats."""
from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError

from config.http_utils import validate_chat_messages, validation_error_message
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
        try:
            validate_chat_messages(value)
        except DRFValidationError as exc:
            raise serializers.ValidationError(validation_error_message(exc)) from exc
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

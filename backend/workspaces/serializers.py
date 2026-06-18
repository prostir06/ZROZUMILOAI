"""Serializers for workspaces."""
from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Workspace

User = get_user_model()


class WorkspaceUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name')
        read_only_fields = fields


class WorkspaceSerializer(serializers.ModelSerializer):
    users = WorkspaceUserSerializer(many=True, read_only=True)
    user_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=User.objects.all(),
        source='users',
        write_only=True,
        required=False,
    )
    model_names = serializers.ListField(
        child=serializers.CharField(max_length=120),
        required=False,
        allow_empty=True,
    )
    temperature = serializers.FloatField(
        min_value=0.0,
        max_value=2.0,
        required=False,
    )

    class Meta:
        model = Workspace
        fields = (
            'id',
            'name',
            'system_prompt',
            'temperature',
            'model_names',
            'users',
            'user_ids',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate_model_names(self, value):
        cleaned = []
        seen = set()
        for name in value:
            trimmed = name.strip()
            if not trimmed or trimmed in seen:
                continue
            seen.add(trimmed)
            cleaned.append(trimmed)
        return cleaned

    def create(self, validated_data):
        users = validated_data.pop('users', [])
        workspace = Workspace.objects.create(**validated_data)
        if users:
            workspace.users.set(users)
        return workspace

    def update(self, instance, validated_data):
        users = validated_data.pop('users', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if users is not None:
            instance.users.set(users)
        return instance


class WorkspaceBriefSerializer(serializers.ModelSerializer):
    """Workspace info for chat selection."""

    class Meta:
        model = Workspace
        fields = (
            'id',
            'name',
            'system_prompt',
            'temperature',
            'model_names',
        )
        read_only_fields = fields

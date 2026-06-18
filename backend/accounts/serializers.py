"""Serializers for user accounts."""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .services import create_api_key

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Public user representation."""

    api_key_prefix = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'is_staff',
            'api_key_prefix',
        )
        read_only_fields = fields

    def get_api_key_prefix(self, obj):
        from .models import ApiKey
        try:
            return f'{obj.api_key.key_prefix}...'
        except ApiKey.DoesNotExist:
            return None


class UserCreateResponseSerializer(UserSerializer):
    """User data with full API key (only on creation)."""

    api_key = serializers.CharField(read_only=True)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ('api_key',)


class RegisterSerializer(serializers.ModelSerializer):
    """Registration serializer with password validation."""

    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = (
            'username',
            'email',
            'password',
            'password_confirm',
            'first_name',
            'last_name',
        )

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError(
                {'password_confirm': 'Паролі не збігаються'},
            )
        validate_password(attrs['password'])
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        user._created_api_key = create_api_key(user)
        return user


class AdminCreateUserSerializer(serializers.ModelSerializer):
    """Admin-only user creation."""

    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = (
            'username',
            'email',
            'password',
            'first_name',
            'last_name',
            'is_staff',
        )

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        user._created_api_key = create_api_key(user)
        return user


class AdminUpdateUserSerializer(serializers.ModelSerializer):
    """Admin-only user update."""

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        required=False,
        allow_blank=True,
    )

    class Meta:
        model = User
        fields = (
            'username',
            'email',
            'password',
            'first_name',
            'last_name',
            'is_staff',
        )

    def validate_password(self, value):
        if value:
            validate_password(value)
        return value

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    """Change password for the current user."""

    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True, min_length=8)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Неправильний поточний пароль')
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError(
                {'new_password_confirm': 'Паролі не збігаються'},
            )
        validate_password(attrs['new_password'], self.context['request'].user)
        return attrs

    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user

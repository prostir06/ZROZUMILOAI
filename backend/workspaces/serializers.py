"""Serializers for workspaces."""
from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import TelegramBot, WidgetToken, Workspace
from .telegram.serializers import TelegramBotSerializer

User = get_user_model()

SEARCH_SOURCE_CHOICES = [choice[0] for choice in Workspace.SearchSource.choices]
LLM_PROVIDER_CHOICES = [choice[0] for choice in Workspace.LLMProvider.choices]


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
    telegram_bots = TelegramBotSerializer(many=True, read_only=True)
    telegram_bot_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=TelegramBot.objects.all(),
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
    meilisearch_api_key = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
    )
    meilisearch_api_key_set = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = (
            'id',
            'name',
            'system_prompt',
            'temperature',
            'model_names',
            'llm_provider',
            'search_source',
            'meilisearch_url',
            'meilisearch_api_key',
            'meilisearch_api_key_set',
            'meilisearch_index_prefix',
            'meilisearch_indexes',
            'meilisearch_course_id',
            'embed_greeting',
            'embed_faq_questions',
            'users',
            'user_ids',
            'telegram_bots',
            'telegram_bot_ids',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def get_meilisearch_api_key_set(self, obj):
        return bool(obj.meilisearch_api_key)

    def validate_model_names(self, value):
        cleaned = []
        seen = set()
        for name in value:
            trimmed = name.strip()
            if not trimmed or trimmed in seen:
                continue
            seen.add(trimmed)
            cleaned.append(trimmed)
        if len(cleaned) > 1:
            raise serializers.ValidationError(
                'Workspace може мати лише одну модель',
            )
        return cleaned

    def validate_llm_provider(self, value):
        if value not in LLM_PROVIDER_CHOICES:
            raise serializers.ValidationError('Невідомий LLM провайдер')
        return value

    def validate_search_source(self, value):
        if value not in SEARCH_SOURCE_CHOICES:
            raise serializers.ValidationError('Невідоме джерело пошуку')
        return value

    def validate_meilisearch_indexes(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError('Очікується список індексів')
        cleaned = []
        for item in value:
            name = str(item).strip()[:100]
            if name:
                cleaned.append(name)
            if len(cleaned) >= 20:
                break
        return cleaned

    def validate_embed_greeting(self, value):
        """Обрізати привітання embed до безпечної довжини."""
        try:
            text = str(value or '').strip()
        except (TypeError, ValueError) as exc:
            raise serializers.ValidationError('Некоректне привітання') from exc
        return text[:500]

    def validate_embed_faq_questions(self, value):
        """Список рядків FAQ для embed (макс. 8 коротких питань)."""
        if value is None or value == '':
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError('FAQ має бути списком рядків')
        cleaned = []
        try:
            for item in value:
                text = str(item).strip()
                if text:
                    cleaned.append(text[:200])
                if len(cleaned) >= 8:
                    break
        except (TypeError, ValueError) as exc:
            raise serializers.ValidationError('Некоректний список FAQ') from exc
        return cleaned

    def validate(self, attrs):
        initial = getattr(self, 'initial_data', {}) or {}
        if 'gemini_api_key' in initial:
            raise serializers.ValidationError({
                'gemini_api_key': 'Gemini більше не підтримується',
            })
        llm_provider = attrs.get(
            'llm_provider',
            getattr(self.instance, 'llm_provider', Workspace.LLMProvider.OLLAMA),
        )
        if llm_provider != Workspace.LLMProvider.OLLAMA:
            raise serializers.ValidationError({
                'llm_provider': 'Підтримується лише Ollama',
            })

        source = attrs.get(
            'search_source',
            getattr(self.instance, 'search_source', Workspace.SearchSource.INTERNAL),
        )
        if source in (
            Workspace.SearchSource.MEILISEARCH,
            Workspace.SearchSource.HYBRID,
        ):
            url = attrs.get(
                'meilisearch_url',
                getattr(self.instance, 'meilisearch_url', ''),
            )
            api_key = attrs.get('meilisearch_api_key')
            from django.conf import settings as django_settings

            has_url = bool(url) or bool(django_settings.MEILISEARCH_URL)
            has_key = (
                (bool(api_key) if api_key is not None else False)
                or bool(getattr(self.instance, 'meilisearch_api_key', ''))
                or bool(django_settings.MEILISEARCH_API_KEY)
            )
            if not has_url:
                raise serializers.ValidationError({
                    'meilisearch_url': (
                        'URL Meilisearch обовʼязковий для цього джерела пошуку'
                    ),
                })
            if not has_key:
                raise serializers.ValidationError({
                    'meilisearch_api_key': (
                        'API key Meilisearch обовʼязковий для цього джерела пошуку'
                    ),
                })
        return attrs

    def _apply_api_key(self, instance, api_key):
        """Зберегти Meilisearch key у зашифрованому вигляді (або очистити)."""
        if api_key is not None:
            from .crypto import encrypt_secret

            instance.meilisearch_api_key = encrypt_secret(api_key)

    def _sync_telegram_bots(self, instance, telegram_bots_or_ids):
        if telegram_bots_or_ids is None:
            return
        bot_ids = [
            b.id if hasattr(b, 'id') else b for b in telegram_bots_or_ids
        ]
        TelegramBot.objects.filter(workspace=instance).exclude(
            id__in=bot_ids
        ).update(workspace=None)
        TelegramBot.objects.filter(id__in=bot_ids).update(workspace=instance)
        if hasattr(instance, '_prefetched_objects_cache'):
            instance._prefetched_objects_cache.pop('telegram_bots', None)

    def create(self, validated_data):
        users = validated_data.pop('users', [])
        api_key = validated_data.pop('meilisearch_api_key', None)
        telegram_bots = validated_data.pop('telegram_bot_ids', None)
        workspace = Workspace.objects.create(**validated_data)
        self._apply_api_key(workspace, api_key)
        if api_key is not None:
            workspace.save(update_fields=['meilisearch_api_key'])
        if users:
            workspace.users.set(users)
        if telegram_bots is not None:
            self._sync_telegram_bots(workspace, telegram_bots)
        return workspace

    def update(self, instance, validated_data):
        users = validated_data.pop('users', None)
        api_key = validated_data.pop('meilisearch_api_key', None)
        telegram_bots = validated_data.pop('telegram_bot_ids', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        self._apply_api_key(instance, api_key)
        instance.save()
        if users is not None:
            instance.users.set(users)
        if telegram_bots is not None:
            self._sync_telegram_bots(instance, telegram_bots)
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
            'llm_provider',
        )
        read_only_fields = fields


class WidgetTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = WidgetToken
        fields = (
            'id',
            'label',
            'openedx_course_id',
            'token_prefix',
            'is_active',
            'created_at',
            'last_used_at',
        )
        read_only_fields = fields


class WidgetTokenCreateSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=100, required=False, allow_blank=True)
    openedx_course_id = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
    )


class WidgetTokenCreateResponseSerializer(WidgetTokenSerializer):
    token = serializers.CharField(read_only=True)

    class Meta(WidgetTokenSerializer.Meta):
        fields = WidgetTokenSerializer.Meta.fields + ('token',)


"""Допоміжні функції контролю доступу до workspace та підготовки чату."""
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Workspace


def get_allowed_model_names(user):
    """
    Повернути дозволені імена моделей для користувача.

    Для staff повертає None (доступ до всіх моделей).
    """
    if user.is_staff:
        return None

    names = set()
    for workspace in user.workspaces.all():
        for model_name in workspace.model_names or []:
            if model_name:
                names.add(model_name)
    return names


def user_can_use_model(user, model_name):
    """Перевірити, чи може користувач використовувати вказану модель."""
    allowed = get_allowed_model_names(user)
    if allowed is None:
        return True
    return model_name in allowed


def get_user_workspaces(user):
    """Return workspaces available to the user in chat."""
    if user.is_staff:
        return Workspace.objects.all()
    return user.workspaces.all()


def get_workspace_for_user(user, workspace_id):
    """Return workspace if the user may use it."""
    if not workspace_id:
        return None

    try:
        workspace = Workspace.objects.get(pk=workspace_id)
    except Workspace.DoesNotExist as exc:
        raise ValidationError({'workspace_id': 'Workspace не знайдено'}) from exc

    if user.is_staff:
        return workspace

    if not workspace.users.filter(pk=user.pk).exists():
        raise PermissionDenied('Немає доступу до цього workspace')

    return workspace


def validate_user_chat_workspace(user, workspace, model_name=''):
    """Validate workspace and model for a saved chat (non-staff rules)."""
    if user.is_staff:
        return workspace

    if not workspace:
        raise ValidationError({'workspace': 'Workspace обов\'язковий'})

    workspace_id = workspace.pk if hasattr(workspace, 'pk') else workspace
    ws = get_workspace_for_user(user, workspace_id)

    if model_name and model_name not in (ws.model_names or []):
        raise ValidationError(
            {'model': 'Модель не призначена для цього workspace'},
        )

    return ws


def resolve_workspace_for_chat(user, model_name, workspace_id=None):
    """Resolve workspace and validate model access."""
    if not user.is_staff and not workspace_id:
        raise ValidationError(
            {'workspace_id': 'Workspace обов\'язковий'},
        )

    if workspace_id:
        workspace = get_workspace_for_user(user, workspace_id)
        if not user.is_staff and model_name not in (workspace.model_names or []):
            raise ValidationError(
                {'model': 'Модель не призначена для цього workspace'},
            )
        return workspace

    if user.is_staff:
        return None

    matches = [
        workspace for workspace in user.workspaces.all()
        if model_name in (workspace.model_names or [])
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValidationError(
            {'workspace_id': 'Оберіть workspace для цієї моделі'},
        )
    return None


def prepare_chat_messages(messages, workspace, rag_query=None, meilisearch_course_id=None):
    """Inject workspace system prompt and optional RAG / Meilisearch context."""
    system_parts = []

    if workspace and workspace.system_prompt.strip():
        system_parts.append(workspace.system_prompt.strip())

    if workspace and rag_query:
        from workspaces.rag.service import format_rag_context, search_workspace_context

        chunks = search_workspace_context(
            workspace,
            rag_query,
            course_id=meilisearch_course_id,
        )
        rag_context = format_rag_context(chunks)
        if rag_context:
            system_parts.append(rag_context)

    if not system_parts:
        return list(messages)

    prompt = '\n\n'.join(system_parts)
    prepared = []
    has_system = False
    for message in messages:
        if message.get('role') == 'system':
            if not has_system:
                prepared.append({'role': 'system', 'content': prompt})
                has_system = True
            continue
        prepared.append(message)

    if not has_system:
        prepared.insert(0, {'role': 'system', 'content': prompt})
    return prepared


def get_ollama_options(workspace):
    """Build Ollama options from workspace settings."""
    if not workspace:
        return None
    try:
        temperature = float(workspace.temperature)
    except (TypeError, ValueError):
        temperature = 0.7
    return {'temperature': temperature}


def get_gemini_api_key(workspace=None):
    """
    API ключ Gemini: спочатку workspace, потім глобальний з .env.

    Ключ workspace може бути зашифрований (enc:v1:...); розшифровуємо
    перед передачею у провайдер.
    """
    from django.conf import settings

    from .crypto import decrypt_secret

    if workspace and workspace.gemini_api_key:
        try:
            return decrypt_secret(workspace.gemini_api_key).strip()
        except Exception:
            return workspace.gemini_api_key.strip()
    return (settings.GEMINI_API_KEY or '').strip()


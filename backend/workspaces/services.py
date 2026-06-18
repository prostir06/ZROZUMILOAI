"""Workspace access helpers."""
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Workspace


def get_allowed_model_names(user):
    """Return allowed model names for user, or None if all models are allowed."""
    if user.is_staff:
        return None

    names = set()
    for workspace in user.workspaces.all():
        for model_name in workspace.model_names or []:
            if model_name:
                names.add(model_name)
    return names


def user_can_use_model(user, model_name):
    """Check whether the user may use the given model."""
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
        if model_name not in (workspace.model_names or []):
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


def prepare_chat_messages(messages, workspace):
    """Inject workspace system prompt for the Ollama request."""
    if not workspace or not workspace.system_prompt.strip():
        return list(messages)

    prompt = workspace.system_prompt.strip()
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
    return {'temperature': workspace.temperature}

import React, { useCallback, useMemo } from 'react';

/**
 * ModelSelector handles workspace switching and LLM model selection
 * with provider badges, supporting both admin (full access) and regular user
 * (workspace-constrained) modes.
 *
 * @param {object} props
 * @param {Array<{ name: string, provider?: string }>} [props.models=[]] - Available LLM models
 * @param {string} [props.selectedModel=''] - Currently selected model name
 * @param {(modelName: string) => void} [props.onSelectModel] - Callback on model change
 * @param {Array<{ id: string|number, name: string, model_names?: string[], llm_provider?: string }>} [props.workspaces=[]]
 * @param {string} [props.selectedWorkspaceId=''] - Currently active workspace ID
 * @param {(workspaceId: string) => void} [props.onSelectWorkspace] - Callback on workspace change
 * @param {boolean} [props.isAdmin=false] - Whether user has admin privileges
 * @param {boolean} [props.workspaceLocked=false] - Whether user is locked to assigned workspace
 */
export default function ModelSelector({
  models = [],
  selectedModel = '',
  onSelectModel,
  workspaces = [],
  selectedWorkspaceId = '',
  onSelectWorkspace,
  isAdmin = false,
  workspaceLocked = false,
}) {
  const activeWorkspace = useMemo(
    () => (workspaces || []).find((ws) => String(ws.id) === String(selectedWorkspaceId)),
    [workspaces, selectedWorkspaceId],
  );

  const workspaceModels = useMemo(
    () => activeWorkspace?.model_names || [],
    [activeWorkspace],
  );

  const isWorkspaceSelectable = isAdmin && !workspaceLocked;

  const availableModels = useMemo(() => {
    const modelList = Array.isArray(models) ? models : [];
    if (isAdmin && !workspaceLocked) {
      return modelList;
    }
    if (!activeWorkspace) {
      return [];
    }
    const provider = activeWorkspace.llm_provider || 'ollama';
    return modelList.filter(
      (model) => workspaceModels.includes(model.name)
        && (model.provider || 'ollama') === provider,
    );
  }, [models, activeWorkspace, isAdmin, workspaceLocked, workspaceModels]);

  const selectedModelObj = useMemo(
    () => (Array.isArray(models) ? models.find((m) => m.name === selectedModel) : null),
    [models, selectedModel],
  );

  const currentProvider = selectedModelObj?.provider
    || activeWorkspace?.llm_provider
    || (selectedModel ? 'ollama' : null);

  const handleWorkspaceChange = useCallback((e) => {
    try {
      onSelectWorkspace?.(e.target.value);
    } catch (err) {
      console.error('Error selecting workspace:', err);
    }
  }, [onSelectWorkspace]);

  const handleModelChange = useCallback((e) => {
    try {
      onSelectModel?.(e.target.value);
    } catch (err) {
      console.error('Error selecting model:', err);
    }
  }, [onSelectModel]);

  return (
    <div className="chat-model-selector" role="region" aria-label="Вибір воркспейсу та моделі">
      {isWorkspaceSelectable ? (
        <>
          <select
            value={selectedWorkspaceId}
            onChange={handleWorkspaceChange}
            className="select chat-model-selector__workspace"
            aria-label="Оберіть workspace"
          >
            <option value="">Без workspace</option>
            {(workspaces || []).map((ws) => (
              <option key={ws.id} value={ws.id}>{ws.name}</option>
            ))}
          </select>

          <select
            value={selectedModel}
            onChange={handleModelChange}
            className="select chat-model-selector__model"
            aria-label="Оберіть модель"
          >
            {(!models || models.length === 0) && <option value="">Немає моделей</option>}
            {(models || []).map((m) => (
              <option key={m.name} value={m.name}>
                {m.name}{m.provider ? ` (${m.provider})` : ''}
              </option>
            ))}
          </select>
        </>
      ) : (
        <>
          {activeWorkspace && (
            <span className="chat-controls__label chat-model-selector__workspace-label">
              {activeWorkspace.name}
            </span>
          )}

          {workspaceModels.length > 1 ? (
            <select
              value={selectedModel}
              onChange={handleModelChange}
              className="select chat-model-selector__model"
              aria-label="Оберіть модель"
            >
              {availableModels.length === 0 && <option value="">Немає моделей</option>}
              {availableModels.map((m) => (
                <option key={m.name} value={m.name}>
                  {m.name}{m.provider ? ` (${m.provider})` : ''}
                </option>
              ))}
            </select>
          ) : (
            selectedModel && (
              <span className="chat-controls__label chat-model-selector__model-label">
                {selectedModel}
              </span>
            )
          )}
        </>
      )}

      {currentProvider && (
        <span
          className="badge chat-model-selector__provider-badge"
          title={`Провайдер: ${currentProvider}`}
        >
          {currentProvider}
        </span>
      )}
    </div>
  );
}

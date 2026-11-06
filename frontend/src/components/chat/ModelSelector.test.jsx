import { describe, it, expect } from 'vitest';
import React from 'react';
import { renderToString } from 'react-dom/server';
import ModelSelector from './ModelSelector';

describe('ModelSelector', () => {
  const models = [
    { name: 'llama3:latest', provider: 'ollama' },
    { name: 'gpt-4o', provider: 'openai' },
  ];
  const workspaces = [
    { id: '1', name: 'HR Department', model_names: ['llama3:latest'], llm_provider: 'ollama' },
    { id: '2', name: 'Legal Dept', model_names: ['gpt-4o'], llm_provider: 'openai' },
  ];

  it('renders workspace select and model select with provider badges for admin', () => {
    const html = renderToString(
      <ModelSelector
        models={models}
        selectedModel="llama3:latest"
        onSelectModel={() => {}}
        workspaces={workspaces}
        selectedWorkspaceId="1"
        onSelectWorkspace={() => {}}
        isAdmin={true}
        workspaceLocked={false}
      />
    );
    expect(html).toContain('HR Department');
    expect(html).toContain('Legal Dept');
    expect(html).toContain('llama3:latest');
    expect(html).toContain('gpt-4o');
    expect(html).toContain('ollama');
  });

  it('renders workspace label and available model for non-admin', () => {
    const html = renderToString(
      <ModelSelector
        models={models}
        selectedModel="llama3:latest"
        onSelectModel={() => {}}
        workspaces={workspaces}
        selectedWorkspaceId="1"
        onSelectWorkspace={() => {}}
        isAdmin={false}
        workspaceLocked={true}
      />
    );
    expect(html).toContain('HR Department');
    expect(html).toContain('llama3:latest');
  });

  it('handles empty models or workspaces lists gracefully', () => {
    const html = renderToString(
      <ModelSelector
        models={[]}
        selectedModel=""
        onSelectModel={() => {}}
        workspaces={[]}
        selectedWorkspaceId=""
        onSelectWorkspace={() => {}}
        isAdmin={true}
        workspaceLocked={false}
      />
    );
    expect(html).toContain('Немає моделей');
  });
});

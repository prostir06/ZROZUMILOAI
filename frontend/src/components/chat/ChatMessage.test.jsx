import { describe, it, expect } from 'vitest';
import React from 'react';
import { renderToString } from 'react-dom/server';
import ChatMessage from './ChatMessage';

describe('ChatMessage', () => {
  it('renders user message with avatar U, role label and content', () => {
    const message = {
      role: 'user',
      content: 'Привіт, як справи?',
    };
    const html = renderToString(<ChatMessage message={message} />);
    expect(html).toContain('chat-message--user');
    expect(html).toContain('Ви');
    expect(html).toContain('Привіт, як справи?');
    expect(html).toContain('U');
  });

  it('renders assistant message with robot avatar and role label', () => {
    const message = {
      role: 'assistant',
      content: 'Привіт! Чим можу допомогти?',
    };
    const html = renderToString(<ChatMessage message={message} />);
    expect(html).toContain('chat-message--assistant');
    expect(html).toContain('chat-message-row--assistant');
    expect(html).toContain('Помічник');
    expect(html).toContain('zrozumilo-assistant.png');
    expect(html).toContain('Привіт! Чим можу допомогти?');
  });

  it('renders typing indicator when assistant message is empty and streaming', () => {
    const message = {
      role: 'assistant',
      content: '',
    };
    const html = renderToString(<ChatMessage message={message} isStreaming={true} />);
    expect(html).toContain('chat-typing');
    expect(html).toContain('Помічник друкує');
  });

  it('renders source citations when message.sources is present', () => {
    const message = {
      role: 'assistant',
      content: 'Відповідь на основі документів',
      sources: [
        { document_name: 'policy.pdf', score: 0.9, content: 'Rules text' },
      ],
    };
    const html = renderToString(<ChatMessage message={message} />);
    expect(html).toContain('policy.pdf');
    expect(html).toContain('90%');
  });

  it('renders feedback buttons for assistant message with logId when not streaming', () => {
    const message = {
      role: 'assistant',
      content: 'Тестова відповідь',
      logId: 'log-123',
    };
    const html = renderToString(<ChatMessage message={message} isStreaming={false} />);
    expect(html).toContain('chat-feedback');
    expect(html).toContain('👍');
    expect(html).toContain('👎');
  });

  it('does not render feedback buttons when streaming is true', () => {
    const message = {
      role: 'assistant',
      content: 'Генерація відповіді...',
      logId: 'log-123',
    };
    const html = renderToString(<ChatMessage message={message} isStreaming={true} />);
    expect(html).not.toContain('chat-feedback');
  });

  it('renders handoff hint and button when needsHandoff is present', () => {
    const message = {
      role: 'assistant',
      content: 'Я не впевнений у відповіді',
      logId: 'log-456',
      needsHandoff: true,
    };
    const html = renderToString(<ChatMessage message={message} />);
    expect(html).toContain('Низька впевненість — можна звернутися до підтримки');
  });

  it('renders nothing when message is null or undefined', () => {
    expect(renderToString(<ChatMessage message={null} />)).toBe('');
    expect(renderToString(<ChatMessage message={undefined} />)).toBe('');
    expect(renderToString(<ChatMessage />)).toBe('');
  });
});

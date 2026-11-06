import { describe, it, expect } from 'vitest';
import React from 'react';
import { renderToString } from 'react-dom/server';
import ChatInput from './ChatInput';

describe('ChatInput', () => {
  it('renders textarea and submit button with arrow', () => {
    const html = renderToString(
      <ChatInput
        input="Привіт"
        setInput={() => {}}
        onSubmit={() => {}}
        onStop={() => {}}
        streaming={false}
        loading={false}
        disabled={false}
      />
    );
    expect(html).toContain('<textarea');
    expect(html).toContain('Привіт');
    expect(html).toContain('Надіслати');
    expect(html).toContain('<svg');
  });

  it('renders Stop button instead of submit button when streaming is true', () => {
    const html = renderToString(
      <ChatInput
        input="Генерується..."
        setInput={() => {}}
        onSubmit={() => {}}
        onStop={() => {}}
        streaming={true}
        loading={false}
        disabled={false}
      />
    );
    expect(html).toContain('Зупинити');
    expect(html).not.toContain('Надіслати');
  });

  it('disables submit button when input is empty or whitespace', () => {
    const html = renderToString(
      <ChatInput
        input="   "
        setInput={() => {}}
        onSubmit={() => {}}
        onStop={() => {}}
        streaming={false}
        loading={false}
        disabled={false}
      />
    );
    expect(html).toContain('disabled');
  });

  it('disables textarea and button when disabled prop is true', () => {
    const html = renderToString(
      <ChatInput
        input="Текст"
        setInput={() => {}}
        onSubmit={() => {}}
        onStop={() => {}}
        streaming={false}
        loading={false}
        disabled={true}
      />
    );
    expect(html).toContain('disabled');
  });
});

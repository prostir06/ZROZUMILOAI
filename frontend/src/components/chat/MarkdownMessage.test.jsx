import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { renderToString } from 'react-dom/server';
import * as markdownModule from 'markdown-to-jsx';
import MarkdownMessage from './MarkdownMessage';

vi.mock('markdown-to-jsx', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    compiler: vi.fn((...args) => actual.compiler(...args)),
  };
});

describe('MarkdownMessage', () => {
  it('renders formatted text and links with target blank and safe rel', () => {
    const markdown = 'Hello **bold** [example](https://example.com)';
    const html = renderToString(<MarkdownMessage content={markdown} />);

    expect(html).toContain('<strong>bold</strong>');
    expect(html).toContain('href="https://example.com"');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer"');
  });

  it('renders fenced code blocks and handles edge cases safely', () => {
    const codeMarkdown = '```python\nprint("hello")\n```';
    const html = renderToString(<MarkdownMessage content={codeMarkdown} />);

    expect(html).toContain('<pre');
    expect(html).toContain('<code');
    expect(html).toContain('print(&quot;hello&quot;)');
  });

  it('handles null or empty content gracefully without throwing', () => {
    const html = renderToString(<MarkdownMessage content={null} />);
    expect(html).toBe('');

    const emptyHtml = renderToString(<MarkdownMessage content="" />);
    expect(emptyHtml).toBe('');

    const undefinedHtml = renderToString(<MarkdownMessage content={undefined} />);
    expect(undefinedHtml).toBe('');
  });

  it('renders code block with language indicator and copy button', () => {
    const codeMarkdown = '```javascript\nconst x = 42;\n```';
    const html = renderToString(<MarkdownMessage content={codeMarkdown} />);

    expect(html).toContain('code-block-wrapper');
    expect(html).toContain('code-block-header');
    expect(html).toContain('javascript');
    expect(html).toContain('code-copy-btn');
    expect(html).toContain('Копіювати');
  });

  it('renders tables with proper structure', () => {
    const tableMarkdown = '| Header 1 | Header 2 |\n|---|---|\n| Cell 1 | Cell 2 |';
    const html = renderToString(<MarkdownMessage content={tableMarkdown} />);

    expect(html).toContain('<table>');
    expect(html).toContain('<th>Header 1</th>');
    expect(html).toContain('<td>Cell 1</td>');
  });

  it('supports isStreaming prop and adds appropriate wrapper class', () => {
    const text = 'Streaming response';
    const html = renderToString(<MarkdownMessage content={text} isStreaming={true} />);

    expect(html).toContain('markdown-body');
    expect(html).toContain('markdown-body--streaming');
  });

  it('falls back to raw text with markdown-fallback class on parse failure', () => {
    markdownModule.compiler.mockImplementationOnce(() => {
      throw new Error('Parse error');
    });

    const html = renderToString(<MarkdownMessage content="Corrupted markdown" />);
    expect(html).toContain('markdown-fallback');
    expect(html).toContain('Corrupted markdown');
  });
});

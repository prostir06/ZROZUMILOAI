import React, { useState, useRef, useEffect, useCallback } from 'react';
import { compiler } from 'markdown-to-jsx';
import '../../styles/markdown.css';

/**
 * Recursively extracts plain text from React nodes / children.
 */
function extractText(node) {
  if (typeof node === 'string') return node;
  if (typeof node === 'number') return String(node);
  if (!node) return '';
  if (Array.isArray(node)) return node.map(extractText).join('');
  if (node.props && node.props.children) return extractText(node.props.children);
  return '';
}

/**
 * Custom link component ensuring safe opening in new tab.
 */
function SafeLink({ href = '', children, ...props }) {
  const isSafe = typeof href === 'string' && /^https?:\/\/|^\/|^mailto:|^tel:|^#/i.test(href);
  const safeHref = isSafe ? href : '#';

  return (
    <a
      href={safeHref}
      target="_blank"
      rel="noopener noreferrer"
      {...props}
    >
      {children}
    </a>
  );
}

/**
 * Custom pre / code block component with language badge and copy-to-clipboard button.
 */
function CodeBlock({ children, ...props }) {
  const [copied, setCopied] = useState(false);
  const timerRef = useRef(null);

  let language = '';
  const child = React.isValidElement(children) ? children : null;
  if (child && child.props && typeof child.props.className === 'string') {
    const match = child.props.className.match(/lang(?:uage)?-([\w-]+)/);
    if (match) {
      language = match[1];
    }
  }

  const codeText = extractText(children);

  const handleCopy = useCallback(async () => {
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(codeText);
        setCopied(true);
        if (timerRef.current) {
          clearTimeout(timerRef.current);
        }
        timerRef.current = setTimeout(() => {
          setCopied(false);
        }, 2000);
      }
    } catch (_err) {
      // Graceful fallback if clipboard API is unavailable
    }
  }, [codeText]);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, []);

  return (
    <div className="code-block-wrapper">
      <div className="code-block-header">
        <span className="code-block-lang">{language || 'code'}</span>
        <button
          type="button"
          className={`code-copy-btn${copied ? ' is-copied' : ''}`}
          onClick={handleCopy}
          aria-label={copied ? 'Скопійовано' : 'Копіювати код'}
        >
          {copied ? 'Скопійовано' : 'Копіювати'}
        </button>
      </div>
      <pre {...props}>{children}</pre>
    </div>
  );
}

const markdownOptions = {
  wrapper: React.Fragment,
  overrides: {
    a: {
      component: SafeLink,
    },
    pre: {
      component: CodeBlock,
    },
  },
};

/**
 * MarkdownMessage renders markdown formatted text with safe links, tables,
 * lists, and code blocks with copy-to-clipboard functionality.
 */
export default function MarkdownMessage({ content, isStreaming = false }) {
  if (content === null || content === undefined || content === '') {
    return null;
  }

  const text = typeof content === 'string' ? content : String(content);

  try {
    return (
      <div className={`markdown-body${isStreaming ? ' markdown-body--streaming' : ''}`}>
        {compiler(text, markdownOptions)}
      </div>
    );
  } catch (_error) {
    return <span className="markdown-fallback">{text}</span>;
  }
}

export { MarkdownMessage };

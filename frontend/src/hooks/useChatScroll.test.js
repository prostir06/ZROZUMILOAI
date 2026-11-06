import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { renderToString } from 'react-dom/server';
import { isNearBottom, useChatScroll } from './useChatScroll';

describe('useChatScroll helpers', () => {
  it('detects near bottom when distance is within threshold', () => {
    const el = { scrollHeight: 1000, scrollTop: 750, clientHeight: 200 };
    expect(isNearBottom(el, 80)).toBe(true);
  });

  it('detects not near bottom when user scrolled up past threshold', () => {
    const el = { scrollHeight: 1000, scrollTop: 600, clientHeight: 200 };
    expect(isNearBottom(el, 80)).toBe(false);
  });

  it('handles invalid or null element safely', () => {
    expect(isNearBottom(null)).toBe(true);
    expect(isNearBottom(undefined)).toBe(true);
    expect(isNearBottom({})).toBe(true);
  });

  it('supports custom threshold values', () => {
    const el = { scrollHeight: 1000, scrollTop: 850, clientHeight: 100 };
    // distance = 1000 - 850 - 100 = 50
    expect(isNearBottom(el, 40)).toBe(false);
    expect(isNearBottom(el, 50)).toBe(true);
    expect(isNearBottom(el, 60)).toBe(true);
  });
});

describe('useChatScroll hook', () => {
  it('initializes with default at-bottom state and exposes expected interface', () => {
    let hookValue;
    const container = {
      scrollHeight: 1000,
      scrollTop: 800,
      clientHeight: 200,
    };
    const endEl = {
      scrollIntoView: vi.fn(),
    };
    const containerRef = { current: container };
    const endRef = { current: endEl };

    function Component() {
      hookValue = useChatScroll({
        containerRef,
        endRef,
        messagesCount: 5,
        isStreaming: false,
      });
      return React.createElement('div');
    }

    renderToString(React.createElement(Component));

    expect(hookValue).toBeDefined();
    expect(hookValue.isAtBottomRef.current).toBe(true);
    expect(hookValue.showScrollButton).toBe(false);
    expect(typeof hookValue.scrollToBottom).toBe('function');
    expect(typeof hookValue.checkScrollPosition).toBe('function');

    // Test scrollToBottom invokes scrollIntoView
    hookValue.scrollToBottom('smooth');
    expect(endEl.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth' });
  });

  it('updates isAtBottomRef and showScrollButton on checkScrollPosition', () => {
    let hookValue;
    const container = {
      scrollHeight: 1000,
      scrollTop: 400,
      clientHeight: 200,
    };
    const containerRef = { current: container };
    const endRef = { current: null };

    function Component() {
      hookValue = useChatScroll({
        containerRef,
        endRef,
        messagesCount: 3,
      });
      return React.createElement('div');
    }

    renderToString(React.createElement(Component));

    hookValue.checkScrollPosition();
    expect(hookValue.isAtBottomRef.current).toBe(false);
  });

  it('supports positional arguments for backwards compatibility', () => {
    let hookValue;
    const container = { scrollHeight: 500, scrollTop: 500, clientHeight: 100 };
    const containerRef = { current: container };
    const endRef = { current: { scrollIntoView: vi.fn() } };

    function Component() {
      hookValue = useChatScroll(containerRef, endRef);
      return React.createElement('div');
    }

    renderToString(React.createElement(Component));
    expect(hookValue.isAtBottomRef.current).toBe(true);
    expect(typeof hookValue.handleScroll).toBe('function');
  });
});

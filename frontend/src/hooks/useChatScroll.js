import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Checks whether the scroll container is scrolled near the bottom within threshold.
 *
 * @param {HTMLElement|null|undefined} element
 * @param {number} [threshold=80]
 * @returns {boolean}
 */
export function isNearBottom(element, threshold = 80) {
  if (!element) {
    return true;
  }
  const { scrollHeight, scrollTop, clientHeight } = element;
  if (
    typeof scrollHeight !== 'number'
    || typeof scrollTop !== 'number'
    || typeof clientHeight !== 'number'
  ) {
    return true;
  }
  const distance = scrollHeight - scrollTop - clientHeight;
  if (Number.isNaN(distance)) {
    return true;
  }
  return distance <= threshold;
}

/**
 * Custom hook to manage chat scroll behavior, near-bottom detection,
 * and auto-scrolling during new messages and streaming.
 *
 * @param {object} options
 * @param {React.RefObject} options.containerRef - Ref to the scrollable chat container
 * @param {React.RefObject} options.endRef - Ref to the bottom marker element
 * @param {number|Array} [options.messagesCount=0] - Number of messages or messages array
 * @param {boolean} [options.isStreaming=false] - Whether AI response is currently streaming
 * @param {number} [options.threshold=80] - Distance in px to consider user at bottom
 * @returns {{
 *   isAtBottomRef: React.MutableRefObject<boolean>,
 *   showScrollButton: boolean,
 *   scrollToBottom: (behavior?: ScrollBehavior) => void,
 *   checkScrollPosition: () => void,
 *   handleScroll: () => void
 * }}
 */
export function useChatScroll(options = {}, maybeEndRef) {
  let containerRef;
  let endRef;
  let messagesCount = 0;
  let isStreaming = false;
  let threshold = 80;

  if (options && (options.current !== undefined || maybeEndRef)) {
    containerRef = options;
    endRef = maybeEndRef;
  } else if (options && typeof options === 'object') {
    containerRef = options.containerRef;
    endRef = options.endRef;
    messagesCount = options.messagesCount ?? 0;
    isStreaming = Boolean(options.isStreaming);
    threshold = typeof options.threshold === 'number' ? options.threshold : 80;
  }

  const isAtBottomRef = useRef(true);
  const [showScrollButton, setShowScrollButton] = useState(false);

  const normalizedCount = typeof messagesCount === 'number'
    ? messagesCount
    : (Array.isArray(messagesCount) ? messagesCount.length : 0);

  const messagesCountRef = useRef(normalizedCount);
  messagesCountRef.current = normalizedCount;

  const checkScrollPosition = useCallback(() => {
    const container = containerRef?.current;
    if (!container) {
      return;
    }
    const atBottom = isNearBottom(container, threshold);
    isAtBottomRef.current = atBottom;
    setShowScrollButton(!atBottom && messagesCountRef.current > 0);
  }, [containerRef, threshold]);

  const scrollToBottom = useCallback((behavior = 'smooth') => {
    if (endRef?.current?.scrollIntoView) {
      endRef.current.scrollIntoView({ behavior });
    } else if (containerRef?.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [endRef, containerRef]);

  // Bind passive scroll listener to avoid blocking main thread
  useEffect(() => {
    const container = containerRef?.current;
    if (!container || !container.addEventListener) {
      return undefined;
    }
    container.addEventListener('scroll', checkScrollPosition, { passive: true });
    return () => {
      container.removeEventListener('scroll', checkScrollPosition);
    };
  }, [containerRef, checkScrollPosition]);

  // Auto-scroll when messages update or streaming starts if user was already at bottom
  useEffect(() => {
    if (isAtBottomRef.current) {
      scrollToBottom(isStreaming ? 'auto' : 'smooth');
    }
    checkScrollPosition();
  }, [normalizedCount, isStreaming, scrollToBottom, checkScrollPosition]);

  return {
    isAtBottomRef,
    showScrollButton,
    scrollToBottom,
    checkScrollPosition,
    handleScroll: checkScrollPosition,
  };
}

export default useChatScroll;

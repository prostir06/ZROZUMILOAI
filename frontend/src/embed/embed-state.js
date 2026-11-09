import { EMBED_FAQ_QUESTIONS, EMBED_GREETING } from './utils.js';

/** Привітання з API (workspace) або дефолт. */
export function getGreetingText(state = {}) {
  const fromApi = (state?.workspace?.greeting || state?.config?.greeting || '').trim();
  return fromApi || EMBED_GREETING;
}

/** FAQ з API або дефолтні питання. */
export function getFaqQuestions(state = {}) {
  const fromApi = state?.workspace?.faq_questions || state?.config?.faqQuestions;
  if (Array.isArray(fromApi) && fromApi.length > 0) {
    return fromApi.map((item) => String(item).trim()).filter(Boolean).slice(0, 8);
  }
  return EMBED_FAQ_QUESTIONS;
}

/** Створення сховища стану для embed-віджета. */
export function createEmbedState(initialState = {}) {
  let state = {
    config: null,
    workspace: null,
    model: '',
    initError: '',
    messages: [],
    isStreaming: false,
    trustedOrigin: null,
    typedGreeting: '',
    ...initialState,
  };

  const listeners = new Set();

  function notify() {
    listeners.forEach((listener) => {
      try {
        listener(state);
      } catch (err) {
        console.error('[ZrozumiloAI Embed State] listener error:', err);
      }
    });
  }

  function getState() {
    return state;
  }

  function setState(patch) {
    const nextPatch = typeof patch === 'function' ? patch(state) : patch;
    state = { ...state, ...nextPatch };
    notify();
    return state;
  }

  function subscribe(listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  }

  function addMessage(msg) {
    const messages = [...state.messages, msg];
    return setState({ messages });
  }

  function updateLastAssistantMessage(patchOrFn) {
    const messages = state.messages.map((msg, index) => {
      if (index === state.messages.length - 1 && msg.role === 'assistant') {
        const patch = typeof patchOrFn === 'function' ? patchOrFn(msg) : patchOrFn;
        return { ...msg, ...patch };
      }
      return msg;
    });
    return setState({ messages });
  }

  function updateFeedback(logId, payload) {
    const messages = state.messages.map((msg) => {
      if (msg.logId !== logId) return msg;
      return {
        ...msg,
        ...(payload.feedback ? { feedback: payload.feedback } : {}),
        ...(payload.needs_handoff ? { needsHandoff: true } : {}),
      };
    });
    return setState({ messages });
  }

  function reset(nextInitial = {}) {
    state = {
      config: null,
      workspace: null,
      model: '',
      initError: '',
      messages: [],
      isStreaming: false,
      trustedOrigin: null,
      typedGreeting: '',
      ...nextInitial,
    };
    notify();
    return state;
  }

  return {
    getState,
    setState,
    subscribe,
    getGreetingText: () => getGreetingText(state),
    getFaqQuestions: () => getFaqQuestions(state),
    addMessage,
    updateLastAssistantMessage,
    updateFeedback,
    reset,
  };
}

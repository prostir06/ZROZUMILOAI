import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useChats } from '../context/ChatContext';
import { useWorkspaces } from '../context/WorkspaceContext';
import { formatBoldText } from '../utils/formatMessage';
import { buildChatTitle } from '../utils/chat';
import { applyStreamChunk } from '../utils/streamMessages';

function ChatPage() {
  const { chatId, workspaceId: routeWorkspaceId } = useParams();
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const { refreshChats } = useChats();
  const { workspaces } = useWorkspaces();
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState('');
  const [messages, setMessages] = useState([]);
  const [title, setTitle] = useState('Новий чат');
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [loadingChat, setLoadingChat] = useState(!!chatId);
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const isAtBottomRef = useRef(true);
  const skipSaveRef = useRef(false);
  const localChatIdRef = useRef(null);
  const streamAbortRef = useRef(null);
  const streamRafRef = useRef(null);
  const streamPendingRef = useRef(null);
  const [showScrollButton, setShowScrollButton] = useState(false);

  const SCROLL_BOTTOM_THRESHOLD = 80;

  const workspaceLocked = !isAdmin;

  const activeWorkspace = useMemo(
    () => workspaces.find((ws) => String(ws.id) === String(selectedWorkspaceId)),
    [workspaces, selectedWorkspaceId],
  );

  const workspaceModels = useMemo(
    () => activeWorkspace?.model_names || [],
    [activeWorkspace],
  );

  const availableModels = useMemo(() => {
    if (isAdmin) {
      return models;
    }
    if (!activeWorkspace) {
      return [];
    }
    const provider = activeWorkspace.llm_provider || 'ollama';
    return models.filter(
      (model) => workspaceModels.includes(model.name)
        && (model.provider || 'ollama') === provider,
    );
  }, [models, activeWorkspace, isAdmin, workspaceModels]);

  useEffect(() => {
    api.getModels().catch(() => ({ models: [] })).then((modelsData) => {
      setModels(modelsData.models || []);
    });
  }, []);

  useEffect(() => {
    if (!routeWorkspaceId || isAdmin || workspaces.length === 0) {
      return;
    }
    const allowed = workspaces.some(
      (workspace) => String(workspace.id) === String(routeWorkspaceId),
    );
    if (!allowed) {
      navigate(`/workspace/${workspaces[0].id}`, { replace: true });
    }
  }, [routeWorkspaceId, workspaces, isAdmin, navigate]);

  useEffect(() => {
    if (routeWorkspaceId) {
      setSelectedWorkspaceId(routeWorkspaceId);
      return;
    }
    if (!chatId && !isAdmin) {
      setSelectedWorkspaceId('');
    }
  }, [routeWorkspaceId, chatId, isAdmin]);

  useEffect(() => {
    if (!workspaceLocked || !activeWorkspace || workspaceModels.length === 0) {
      return;
    }
    if (workspaceModels.includes(selectedModel)) {
      return;
    }
    setSelectedModel(workspaceModels[0]);
  }, [workspaceLocked, activeWorkspace, workspaceModels, selectedModel]);

  useEffect(() => {
    if (workspaceLocked || !selectedModel || selectedWorkspaceId) {
      return;
    }
    const matches = workspaces.filter((ws) => ws.model_names?.includes(selectedModel));
    if (matches.length === 1) {
      setSelectedWorkspaceId(String(matches[0].id));
    }
  }, [selectedModel, workspaces, selectedWorkspaceId, workspaceLocked]);

  useEffect(() => {
    if (availableModels.length === 0) {
      return;
    }
    const isCurrentAvailable = availableModels.some((model) => model.name === selectedModel);
    if (!isCurrentAvailable) {
      setSelectedModel(availableModels[0].name);
    }
  }, [availableModels, selectedModel]);

  const checkScrollPosition = useCallback(() => {
    const container = messagesContainerRef.current;
    if (!container) {
      return;
    }
    const distance = container.scrollHeight - container.scrollTop - container.clientHeight;
    const atBottom = distance <= SCROLL_BOTTOM_THRESHOLD;
    isAtBottomRef.current = atBottom;
    setShowScrollButton(!atBottom && messages.length > 0);
  }, [messages.length]);

  const scrollToBottom = useCallback((behavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  }, []);

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) {
      return undefined;
    }
    container.addEventListener('scroll', checkScrollPosition, { passive: true });
    return () => container.removeEventListener('scroll', checkScrollPosition);
  }, [checkScrollPosition]);

  useEffect(() => {
    if (isAtBottomRef.current) {
      scrollToBottom(streaming ? 'auto' : 'smooth');
    }
    checkScrollPosition();
  }, [messages, streaming, scrollToBottom, checkScrollPosition]);

  useEffect(() => {
    if (!chatId) {
      setMessages([]);
      setTitle('Новий чат');
      if (!routeWorkspaceId) {
        setSelectedWorkspaceId('');
      }
      setLoadingChat(false);
      skipSaveRef.current = true;
      localChatIdRef.current = null;
      return undefined;
    }

    if (String(localChatIdRef.current) === chatId) {
      localChatIdRef.current = null;
      setLoadingChat(false);
      return undefined;
    }

    setLoadingChat(true);
    skipSaveRef.current = true;

    api.getChat(chatId)
      .then((data) => {
        setMessages(data.messages || []);
        setTitle(data.title || 'Новий чат');
        if (data.model) {
          setSelectedModel(data.model);
        }
        if (data.workspace) {
          setSelectedWorkspaceId(String(data.workspace));
        }
      })
      .catch(() => navigate('/', { replace: true }))
      .finally(() => {
        setLoadingChat(false);
        setTimeout(() => {
          skipSaveRef.current = false;
        }, 0);
      });

    return undefined;
  }, [chatId, navigate, routeWorkspaceId]);

  useEffect(() => {
    if (!chatId || loadingChat || streaming || skipSaveRef.current) return undefined;
    if (messages.length === 0) return undefined;

    const timer = setTimeout(() => {
      // P0: не оновлюємо sidebar на кожен autosave — лише зберігаємо чат.
      api.updateChat(chatId, {
        title,
        model: selectedModel,
        workspace: selectedWorkspaceId ? Number(selectedWorkspaceId) : null,
        messages,
      }).catch(() => {
        /* тихий retry наступним debounce; UI статус можна додати пізніше */
      });
    }, 500);

    return () => clearTimeout(timer);
  }, [
    chatId,
    messages,
    title,
    selectedModel,
    selectedWorkspaceId,
    loadingChat,
    streaming,
  ]);

  /** Оновити лише останнє assistant-повідомлення (з throttle через rAF). */
  const patchLastAssistant = useCallback((contentOrError, { isError = false } = {}) => {
    streamPendingRef.current = { contentOrError, isError };
    if (streamRafRef.current) {
      return;
    }
    streamRafRef.current = requestAnimationFrame(() => {
      streamRafRef.current = null;
      const pending = streamPendingRef.current;
      if (!pending) {
        return;
      }
      streamPendingRef.current = null;
      setMessages((prev) => {
        if (!prev.length) {
          return prev;
        }
        const last = prev[prev.length - 1];
        if (last.role !== 'assistant') {
          return prev;
        }
        const nextContent = pending.isError
          ? `Помилка: ${pending.contentOrError}`
          : last.content + pending.contentOrError;
        if (nextContent === last.content) {
          return prev;
        }
        return [...prev.slice(0, -1), { ...last, content: nextContent }];
      });
    });
  }, []);

  const handleSend = async (event) => {
    event.preventDefault();
    if (!input.trim() || !selectedModel || loading) return;

    if (workspaceLocked && !selectedWorkspaceId) {
      return;
    }

    // Скасувати попередній стрім, якщо ще триває.
    try {
      streamAbortRef.current?.abort();
    } catch {
      /* ignore */
    }
    const abortController = new AbortController();
    streamAbortRef.current = abortController;

    const userMessage = { role: 'user', content: input.trim() };
    const newMessages = [...messages, userMessage];
    const chatTitle = title === 'Новий чат' ? buildChatTitle(userMessage.content) : title;
    const workspaceId = selectedWorkspaceId ? Number(selectedWorkspaceId) : null;

    setMessages(newMessages);
    setInput('');
    setTitle(chatTitle);
    setLoading(true);
    setStreaming(true);

    const assistantMessage = { role: 'assistant', content: '' };
    setMessages([...newMessages, assistantMessage]);

    let activeChatId = chatId;

    try {
      if (!activeChatId) {
        const created = await api.createChat({
          title: chatTitle,
          model: selectedModel,
          workspace: workspaceId,
          messages: newMessages,
        });
        activeChatId = String(created.id);
        localChatIdRef.current = activeChatId;
        skipSaveRef.current = true;
        navigate(`/chat/${created.id}`, { replace: true });
        refreshChats();
      }

      await api.chatStream(
        selectedModel,
        newMessages,
        (chunk) => {
          // Текст — через rAF; meta (sources/logId) — окремо без повторного content.
          if (chunk.message?.content) {
            patchLastAssistant(chunk.message.content);
          }
          if (chunk.error) {
            patchLastAssistant(chunk.error, { isError: true });
          }
          if (
            chunk.sources
            || chunk.log_id != null
            || typeof chunk.needs_handoff === 'boolean'
          ) {
            setMessages((prev) => applyStreamChunk(prev, chunk, { metaOnly: true }));
          }
        },
        workspaceId,
        { signal: abortController.signal },
      );
    } catch (err) {
      if (err?.name === 'AbortError') {
        return;
      }
      patchLastAssistant(err.message || 'Помилка чату', { isError: true });
      // Форсувати негайне застосування pending після помилки.
      if (streamRafRef.current) {
        cancelAnimationFrame(streamRafRef.current);
        streamRafRef.current = null;
      }
      setMessages((prev) => {
        if (!prev.length) return prev;
        const last = prev[prev.length - 1];
        if (last.role !== 'assistant') return prev;
        return [
          ...prev.slice(0, -1),
          { ...last, content: `Помилка: ${err.message}` },
        ];
      });
    } finally {
      setLoading(false);
      setStreaming(false);
      skipSaveRef.current = false;
      streamAbortRef.current = null;
      // Один refresh sidebar після завершення стріму (не на кожен chunk/autosave).
      if (activeChatId) {
        refreshChats();
      }
    }
  };

  const flushStreamPending = useCallback(() => {
    if (streamRafRef.current) {
      cancelAnimationFrame(streamRafRef.current);
      streamRafRef.current = null;
    }
    const pending = streamPendingRef.current;
    streamPendingRef.current = null;
    if (!pending) {
      return;
    }
    setMessages((prev) => {
      if (!prev.length) {
        return prev;
      }
      const last = prev[prev.length - 1];
      if (last.role !== 'assistant') {
        return prev;
      }
      const nextContent = pending.isError
        ? `Помилка: ${pending.contentOrError}`
        : last.content + pending.contentOrError;
      if (nextContent === last.content) {
        return prev;
      }
      return [...prev.slice(0, -1), { ...last, content: nextContent }];
    });
  }, []);

  const handleStopGeneration = useCallback(() => {
    try {
      streamAbortRef.current?.abort();
    } catch {
      /* AbortController.abort() не повинен кидати — захист від нестандартних поліфілів */
    }
    flushStreamPending();
    setLoading(false);
    setStreaming(false);
  }, [flushStreamPending]);

  const handleFeedback = useCallback(async (msg, feedback) => {
    if (!msg?.logId) return;
    try {
      await api.submitChatFeedback(msg.logId, { feedback });
      setMessages((prev) => prev.map((item) => (
        item.logId === msg.logId ? { ...item, feedback } : item
      )));
    } catch (err) {
      window.alert(err.message || 'Не вдалося зберегти відгук');
    }
  }, []);

  const handleRequestHandoff = useCallback(async (msg) => {
    if (!msg?.logId) return;
    try {
      await api.submitChatFeedback(msg.logId, { needs_handoff: true });
      setMessages((prev) => prev.map((item) => (
        item.logId === msg.logId ? { ...item, needsHandoff: true } : item
      )));
    } catch (err) {
      window.alert(err.message || 'Не вдалося надіслати запит до підтримки');
    }
  }, []);

  const handleClear = useCallback(async () => {
    if (chatId) {
      if (!window.confirm('Видалити цей збережений чат?')) return;
      try {
        await api.deleteChat(chatId);
        refreshChats();
        if (selectedWorkspaceId) {
          navigate(`/workspace/${selectedWorkspaceId}`, { replace: true });
        } else {
          navigate('/', { replace: true });
        }
      } catch {
        /* ignore */
      }
      return;
    }
    setMessages([]);
    setTitle('Новий чат');
  }, [chatId, navigate, refreshChats, selectedWorkspaceId]);

  if (loadingChat) {
    return (
      <div className="page page-loading">
        <div className="spinner" aria-label="Завантаження чату" />
      </div>
    );
  }

  if (workspaceLocked && !selectedWorkspaceId && !chatId) {
    return (
      <div className="page">
        <header className="page__header">
          <h2>Оберіть workspace</h2>
          <p>Виберіть workspace у боковій панелі, щоб почати чат.</p>
        </header>
      </div>
    );
  }

  const headerSubtitle = workspaceLocked
    ? 'Почніть діалог у призначеному workspace'
    : 'Оберіть workspace, модель та почніть діалог';

  return (
    <div className="page page--chat">
      <header className="page__header page__header--row">
        <div>
          <h2>{title}</h2>
          <p>{headerSubtitle}</p>
        </div>
        <div className="chat-controls">
          {isAdmin ? (
            <>
              <select
                value={selectedWorkspaceId}
                onChange={(e) => {
                  const value = e.target.value;
                  setSelectedWorkspaceId(value);
                  if (value) {
                    navigate(`/workspace/${value}`, { replace: true });
                    const workspace = workspaces.find((ws) => String(ws.id) === value);
                    if (workspace?.model_names?.[0]) {
                      setSelectedModel(workspace.model_names[0]);
                    }
                  } else {
                    navigate('/', { replace: true });
                  }
                }}
                className="select"
                aria-label="Оберіть workspace"
              >
                <option value="">Без workspace</option>
                {workspaces.map((ws) => (
                  <option key={ws.id} value={ws.id}>{ws.name}</option>
                ))}
              </select>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="select"
                aria-label="Оберіть модель"
              >
                {models.length === 0 && <option value="">Немає моделей</option>}
                {models.map((m) => (
                  <option key={m.name} value={m.name}>{m.name}</option>
                ))}
              </select>
            </>
          ) : (
            <>
              {activeWorkspace && (
                <span className="chat-controls__label">{activeWorkspace.name}</span>
              )}
              {workspaceModels.length > 1 ? (
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  className="select"
                  aria-label="Оберіть модель"
                >
                  {availableModels.length === 0 && <option value="">Немає моделей</option>}
                  {availableModels.map((m) => (
                    <option key={m.name} value={m.name}>{m.name}</option>
                  ))}
                </select>
              ) : (
                selectedModel && (
                  <span className="chat-controls__label">{selectedModel}</span>
                )
              )}
            </>
          )}
          <button type="button" className="btn btn--ghost" onClick={handleClear}>
            {chatId ? 'Видалити' : 'Очистити'}
          </button>
        </div>
      </header>

      {activeWorkspace && (
        <div className="chat-workspace-meta">
          <span>Температура: {activeWorkspace.temperature ?? 0.7}</span>
          {activeWorkspace.system_prompt && (
            <span className="chat-workspace-meta__prompt" title={activeWorkspace.system_prompt}>
              Промпт налаштовано
            </span>
          )}
        </div>
      )}

      <div className="chat-container">
        <div
          className="chat-messages"
          ref={messagesContainerRef}
          role="log"
          aria-live="polite"
        >
          {messages.length === 0 && (
            <div className="chat-empty">
              <p>Напишіть повідомлення, щоб почати розмову</p>
            </div>
          )}
          {messages.map((msg, index) => {
            const isPendingAssistant = (
              streaming
              && index === messages.length - 1
              && msg.role === 'assistant'
              && !msg.content.trim()
            );

            if (msg.role === 'assistant') {
              return (
                <div key={`${msg.role}-${index}`} className="chat-message-row chat-message-row--assistant">
                  <img
                    src="/zrozumilo-assistant.png"
                    alt=""
                    className="chat-message__avatar"
                    width={28}
                    height={28}
                  />
                  {isPendingAssistant ? (
                    <div className="chat-typing" aria-label="Помічник друкує">
                      <span /><span /><span />
                    </div>
                  ) : (
                    <div className={`chat-message chat-message--${msg.role}`}>
                      <div className="chat-message__role">Помічник</div>
                      <div className="chat-message__content">
                        {formatBoldText(msg.content)}
                      </div>
                      {Array.isArray(msg.sources) && msg.sources.length > 0 && (
                        <div className="chat-sources">
                          <div className="chat-sources__title">Джерела</div>
                          <ul>
                            {msg.sources.map((source, srcIndex) => (
                              <li key={`${source.document_name}-${srcIndex}`}>
                                <strong>{source.document_name}</strong>
                                {source.excerpt ? (
                                  <span className="chat-sources__excerpt">
                                    {' '}
                                    —
                                    {' '}
                                    {source.excerpt}
                                  </span>
                                ) : null}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {(msg.needsHandoff || msg.logId) && !streaming && (
                        <div className="chat-feedback">
                          {msg.needsHandoff && (
                            <span className="chat-feedback__hint">
                              Низька впевненість — можна звернутися до підтримки
                            </span>
                          )}
                          {msg.logId && (
                            <>
                              <button
                                type="button"
                                className={`btn btn--ghost btn--sm${msg.feedback === 'up' ? ' is-active' : ''}`}
                                onClick={() => handleFeedback(msg, 'up')}
                                aria-label="Корисна відповідь"
                                aria-pressed={msg.feedback === 'up'}
                              >
                                👍
                              </button>
                              <button
                                type="button"
                                className={`btn btn--ghost btn--sm${msg.feedback === 'down' ? ' is-active' : ''}`}
                                onClick={() => handleFeedback(msg, 'down')}
                                aria-label="Некорисна відповідь"
                                aria-pressed={msg.feedback === 'down'}
                              >
                                👎
                              </button>
                              {!msg.needsHandoff && (
                                <button
                                  type="button"
                                  className="btn btn--ghost btn--sm"
                                  onClick={() => handleRequestHandoff(msg)}
                                  aria-label="Запросити допомогу людини"
                                >
                                  До людини
                                </button>
                              )}
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            }

            return (
              <div
                key={`${msg.role}-${index}`}
                className={`chat-message chat-message--${msg.role}`}
              >
                <div className="chat-message__role">Ви</div>
                <div className="chat-message__content">{msg.content}</div>
              </div>
            );
          })}
          {streaming && messages[messages.length - 1]?.role !== 'assistant' && (
            <div className="chat-message-row chat-message-row--assistant">
              <img
                src="/zrozumilo-assistant.png"
                alt=""
                className="chat-message__avatar"
                width={28}
                height={28}
              />
              <div className="chat-typing" aria-label="Помічник друкує">
                <span /><span /><span />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {showScrollButton && (
          <button
            type="button"
            className="chat-scroll-bottom"
            onClick={() => scrollToBottom()}
            aria-label="До останнього повідомлення"
            title="До останнього повідомлення"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M7.41 8.59 12 13.17l4.59-4.58L18 10l-6 6-6-6z" />
            </svg>
          </button>
        )}

        <form className="chat-input" onSubmit={handleSend}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Введіть повідомлення..."
            aria-label="Текст повідомлення"
            rows={2}
            disabled={!selectedModel || loading || (workspaceLocked && !selectedWorkspaceId)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend(e);
              }
            }}
          />
          <button
            type="submit"
            className="btn btn--primary"
            disabled={
              !input.trim()
              || !selectedModel
              || loading
              || (workspaceLocked && !selectedWorkspaceId)
            }
          >
            Надіслати
          </button>
          {streaming && (
            <button
              type="button"
              className="btn btn--ghost"
              onClick={handleStopGeneration}
              aria-label="Зупинити генерацію відповіді"
            >
              Зупинити
            </button>
          )}
        </form>
      </div>
    </div>
  );
}

export default ChatPage;

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useChats } from '../context/ChatContext';
import { useWorkspaces } from '../context/WorkspaceContext';
import { formatBoldText } from '../utils/formatMessage';
import { buildChatTitle } from '../utils/chat';

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
  const skipSaveRef = useRef(false);
  const localChatIdRef = useRef(null);

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
    return models.filter((model) => workspaceModels.includes(model.name));
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

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

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
      api.updateChat(chatId, {
        title,
        model: selectedModel,
        workspace: selectedWorkspaceId ? Number(selectedWorkspaceId) : null,
        messages,
      })
        .then(() => refreshChats())
        .catch(() => {});
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
    refreshChats,
  ]);

  const handleSend = async (event) => {
    event.preventDefault();
    if (!input.trim() || !selectedModel || loading) return;

    if (workspaceLocked && !selectedWorkspaceId) {
      return;
    }

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
          if (chunk.message?.content) {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last.role === 'assistant') {
                updated[updated.length - 1] = {
                  ...last,
                  content: last.content + chunk.message.content,
                };
              }
              return updated;
            });
          }
          if (chunk.error) {
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                role: 'assistant',
                content: `Помилка: ${chunk.error}`,
              };
              return updated;
            });
          }
        },
        workspaceId,
      );
    } catch (err) {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: 'assistant',
          content: `Помилка: ${err.message}`,
        };
        return updated;
      });
    } finally {
      setLoading(false);
      setStreaming(false);
      skipSaveRef.current = false;
      if (activeChatId) {
        refreshChats();
      }
    }
  };

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
        <div className="chat-messages" role="log" aria-live="polite">
          {messages.length === 0 && (
            <div className="chat-empty">
              <p>Напишіть повідомлення, щоб почати розмову</p>
            </div>
          )}
          {messages.map((msg, index) => (
            <div
              key={`${msg.role}-${index}`}
              className={`chat-message chat-message--${msg.role}`}
            >
              <div className="chat-message__role">
                {msg.role === 'user' ? 'Ви' : 'Помічник'}
              </div>
              <div className="chat-message__content">
                {msg.role === 'assistant'
                  ? formatBoldText(msg.content)
                  : msg.content}
              </div>
            </div>
          ))}
          {streaming && (
            <div className="chat-typing" aria-label="Помічник друкує">
              <span /><span /><span />
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form className="chat-input" onSubmit={handleSend}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Введіть повідомлення..."
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
        </form>
      </div>
    </div>
  );
}

export default ChatPage;

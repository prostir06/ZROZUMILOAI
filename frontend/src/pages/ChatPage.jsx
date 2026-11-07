import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useChats } from '../context/ChatContext';
import { useWorkspaces } from '../context/WorkspaceContext';
import { useChatScroll } from '../hooks/useChatScroll';
import { useChatStream } from '../hooks/useChatStream';
import ChatInput from '../components/chat/ChatInput';
import ChatMessage from '../components/chat/ChatMessage';
import ModelSelector from '../components/chat/ModelSelector';
import { buildChatTitle } from '../utils/chat';
import { formatChatError } from '../utils/chatError';
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
  const [loadingChat, setLoadingChat] = useState(!!chatId);

  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const skipSaveRef = useRef(false);
  const localChatIdRef = useRef(null);

  const workspaceLocked = !isAdmin;

  const { streaming, loading, startStream, abortStream } = useChatStream();

  const { isAtBottomRef, showScrollButton, scrollToBottom } = useChatScroll({
    containerRef: messagesContainerRef,
    endRef: messagesEndRef,
    messagesCount: messages.length,
    isStreaming: streaming,
  });

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
    api.getModels().catch((err) => {
      console.error('Failed to load models for chat:', err);
      return { models: [] };
    }).then((modelsData) => {
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
      .catch((err) => {
        console.error('Failed to load chat history:', err);
        navigate('/', { replace: true });
      })
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
      // P0: do not refresh sidebar on each autosave — persist chat payload only.
      api.updateChat(chatId, {
        title,
        model: selectedModel,
        workspace: selectedWorkspaceId ? Number(selectedWorkspaceId) : null,
        messages,
      }).catch((err) => {
        // Warning level: will retry naturally on next message/state debounce
        console.warn('Autosave chat failed (will retry on next debounce):', err);
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

  const handleSelectWorkspace = useCallback((value) => {
    setSelectedWorkspaceId(value);
    if (value) {
      navigate(`/workspace/${value}`, { replace: true });
      const ws = workspaces.find((w) => String(w.id) === String(value));
      if (ws?.model_names?.[0]) {
        setSelectedModel(ws.model_names[0]);
      }
    } else {
      navigate('/', { replace: true });
    }
  }, [navigate, workspaces]);

  const handleSend = async (event) => {
    event?.preventDefault?.();
    if (!input.trim() || !selectedModel || loading) return;

    if (workspaceLocked && !selectedWorkspaceId) {
      return;
    }

    const userMessage = { role: 'user', content: input.trim() };
    const newMessages = [...messages, userMessage];
    const chatTitle = title === 'Новий чат' ? buildChatTitle(userMessage.content) : title;
    const workspaceId = selectedWorkspaceId ? Number(selectedWorkspaceId) : null;

    setMessages([...newMessages, { role: 'assistant', content: '' }]);
    setInput('');
    setTitle(chatTitle);

    let activeChatId = chatId;

    await startStream({
      apiCall: async (signal, handleChunk) => {
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
          handleChunk,
          workspaceId,
          { signal },
        );
      },
      onChunk: (textChunk) => {
        setMessages((prev) => {
          if (!prev.length) return prev;
          const last = prev[prev.length - 1];
          if (last.role !== 'assistant') return prev;
          return [
            ...prev.slice(0, -1),
            { ...last, content: last.content + textChunk },
          ];
        });
        if (isAtBottomRef.current) {
          scrollToBottom('auto');
        }
      },
      onSources: (sources) => {
        setMessages((prev) => applyStreamChunk(prev, { sources }, { metaOnly: true }));
      },
      onMeta: (meta) => {
        setMessages((prev) => applyStreamChunk(prev, meta, { metaOnly: true }));
      },
      onError: (err) => {
        setMessages((prev) => {
          if (!prev.length) return prev;
          const last = prev[prev.length - 1];
          if (last.role !== 'assistant') return prev;
          return [
            ...prev.slice(0, -1),
            { ...last, content: formatChatError(err) },
          ];
        });
      },
      onDone: () => {
        skipSaveRef.current = false;
        if (activeChatId) {
          refreshChats();
        }
      },
    });
  };

  const handleStopGeneration = useCallback(() => {
    abortStream();
    skipSaveRef.current = false;
  }, [abortStream]);

  const handleFeedback = useCallback(async (msg, feedback) => {
    if (!msg?.logId) return;
    try {
      await api.submitChatFeedback(msg.logId, { feedback });
      setMessages((prev) => prev.map((item) => (
        item.logId === msg.logId ? { ...item, feedback } : item
      )));
    } catch (err) {
      console.error('Failed to submit chat feedback:', err);
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
      console.error('Failed to request handoff:', err);
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
      } catch (err) {
        console.error('Failed to delete chat:', err);
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
          <ModelSelector
            models={models}
            selectedModel={selectedModel}
            onSelectModel={setSelectedModel}
            workspaces={workspaces}
            selectedWorkspaceId={selectedWorkspaceId}
            onSelectWorkspace={handleSelectWorkspace}
            isAdmin={isAdmin}
            workspaceLocked={workspaceLocked}
          />
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
          {messages.map((msg, index) => (
            <ChatMessage
              key={`${msg.role}-${index}`}
              message={msg}
              onFeedback={handleFeedback}
              onRequestHandoff={handleRequestHandoff}
              isStreaming={streaming && index === messages.length - 1 && msg.role === 'assistant'}
            />
          ))}
          {streaming && messages[messages.length - 1]?.role !== 'assistant' && (
            <div className="chat-message-row chat-message-row--assistant">
              <img
                src="/zrozumilo-assistant.png"
                alt="Помічник"
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

        <ChatInput
          input={input}
          setInput={setInput}
          onSubmit={handleSend}
          onStop={handleStopGeneration}
          streaming={streaming}
          loading={loading}
          disabled={!selectedModel || (workspaceLocked && !selectedWorkspaceId)}
        />
      </div>
    </div>
  );
}

export default ChatPage;

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import { useAuth } from './AuthContext';

const ChatContext = createContext(null);

export function ChatProvider({ children }) {
  const { isAuthenticated } = useAuth();
  const [chats, setChats] = useState([]);
  const [loading, setLoading] = useState(false);

  const refreshChats = useCallback(async () => {
    if (!isAuthenticated) {
      setChats([]);
      return;
    }

    setLoading(true);
    try {
      const data = await api.getChats();
      setChats(data);
    } catch {
      setChats([]);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    refreshChats();
  }, [refreshChats]);

  const value = useMemo(
    () => ({ chats, loading, refreshChats }),
    [chats, loading, refreshChats],
  );

  return (
    <ChatContext.Provider value={value}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChats() {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChats must be used within ChatProvider');
  }
  return context;
}

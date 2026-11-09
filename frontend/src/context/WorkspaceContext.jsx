import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import { useAuth } from './AuthContext';

const WorkspaceContext = createContext(null);

export function WorkspaceProvider({ children }) {
  const { isAuthenticated } = useAuth();
  const [workspaces, setWorkspaces] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const refreshWorkspaces = useCallback(async () => {
    if (!isAuthenticated) {
      setWorkspaces([]);
      setError('');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const data = await api.getMyWorkspaces();
      setWorkspaces(data);
    } catch (err) {
      console.error('Failed to load user workspaces:', err);
      setError(err.message || 'Не вдалося завантажити робочі простори');
      setWorkspaces([]);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    refreshWorkspaces();
  }, [refreshWorkspaces]);

  const value = useMemo(
    () => ({ workspaces, loading, error, refreshWorkspaces }),
    [workspaces, loading, error, refreshWorkspaces],
  );

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspaces() {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error('useWorkspaces must be used within WorkspaceProvider');
  }
  return context;
}

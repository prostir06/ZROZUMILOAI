import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useWorkspaces } from '../context/WorkspaceContext';
import ChatPage from './ChatPage';

function NoWorkspacePage() {
  return (
    <div className="page">
      <header className="page__header">
        <h2>Немає доступних workspace</h2>
        <p>Зверніться до адміністратора, щоб отримати доступ до workspace.</p>
      </header>
    </div>
  );
}

function ChatHomePage() {
  const { isAdmin } = useAuth();
  const { workspaces, loading } = useWorkspaces();

  if (isAdmin) {
    return <ChatPage />;
  }

  if (loading) {
    return (
      <div className="page page-loading">
        <div className="spinner" aria-label="Завантаження" />
      </div>
    );
  }

  if (workspaces.length === 0) {
    return <NoWorkspacePage />;
  }

  return <Navigate to={`/workspace/${workspaces[0].id}`} replace />;
}

export default ChatHomePage;

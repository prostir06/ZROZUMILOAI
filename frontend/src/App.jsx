import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import ChatHomePage from './pages/ChatHomePage';
import ChatPage from './pages/ChatPage';
import AppearancePage from './pages/AppearancePage';
import AdminLayout from './components/AdminLayout';
import ProfileLayout from './components/ProfileLayout';
import PasswordPage from './pages/PasswordPage';

// P1: admin-сторінки в окремих chunk для меншого initial bundle.
const UsersPage = lazy(() => import('./pages/UsersPage'));
const BackupPage = lazy(() => import('./pages/BackupPage'));
const ModelsPage = lazy(() => import('./pages/ModelsPage'));
const WorkspacesPage = lazy(() => import('./pages/WorkspacesPage'));
const WorkspaceChatsPage = lazy(() => import('./pages/WorkspaceChatsPage'));

function RouteFallback() {
  return (
    <div className="loading-screen">
      <div className="spinner" role="status" aria-label="Завантаження" />
    </div>
  );
}

function PrivateRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <RouteFallback />;
  }

  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

function AdminRoute({ children }) {
  const { isAdmin, loading } = useAuth();

  if (loading) return null;
  return isAdmin ? children : <Navigate to="/" replace />;
}

function RegisterRoute() {
  const { isAuthenticated, allowRegistration, loading } = useAuth();

  if (loading || allowRegistration === null) {
    return <RouteFallback />;
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  if (!allowRegistration) {
    return <Navigate to="/login" replace />;
  }

  return <RegisterPage />;
}

function App() {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <RouteFallback />;
  }

  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route
          path="/login"
          element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />}
        />
        <Route path="/register" element={<RegisterRoute />} />
        <Route
          path="/"
          element={(
            <PrivateRoute>
              <Layout />
            </PrivateRoute>
          )}
        >
          <Route index element={<ChatHomePage />} />
          <Route path="workspace/:workspaceId" element={<ChatPage />} />
          <Route path="chat/:chatId" element={<ChatPage />} />
          <Route path="appearance" element={<Navigate to="/profile/appearance" replace />} />
          <Route path="profile" element={<ProfileLayout />}>
            <Route index element={<Navigate to="/profile/appearance" replace />} />
            <Route path="appearance" element={<AppearancePage />} />
            <Route path="password" element={<PasswordPage />} />
          </Route>
          <Route path="models" element={<Navigate to="/admin/models" replace />} />
          <Route path="users" element={<Navigate to="/admin/users" replace />} />
          <Route path="backups" element={<Navigate to="/admin/backups" replace />} />
          <Route
            path="admin"
            element={(
              <AdminRoute>
                <AdminLayout />
              </AdminRoute>
            )}
          >
            <Route index element={<Navigate to="/admin/workspaces" replace />} />
            <Route path="workspaces" element={<WorkspacesPage />} />
            <Route path="chats" element={<WorkspaceChatsPage />} />
            <Route path="models" element={<ModelsPage />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="backups" element={<BackupPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}

export default App;

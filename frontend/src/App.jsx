import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import ChatHomePage from './pages/ChatHomePage';
import ChatPage from './pages/ChatPage';
import AppearancePage from './pages/AppearancePage';
import UsersPage from './pages/UsersPage';
import BackupPage from './pages/BackupPage';
import ModelsPage from './pages/ModelsPage';
import WorkspacesPage from './pages/WorkspacesPage';
import AdminLayout from './components/AdminLayout';
import ProfileLayout from './components/ProfileLayout';
import PasswordPage from './pages/PasswordPage';

function PrivateRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="spinner" aria-label="Завантаження" />
      </div>
    );
  }

  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

function AdminRoute({ children }) {
  const { isAdmin, loading } = useAuth();

  if (loading) return null;
  return isAdmin ? children : <Navigate to="/" replace />;
}

function App() {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="spinner" aria-label="Завантаження" />
      </div>
    );
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route
        path="/register"
        element={isAuthenticated ? <Navigate to="/" replace /> : <RegisterPage />}
      />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <Layout />
          </PrivateRoute>
        }
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
          element={
            <AdminRoute>
              <AdminLayout />
            </AdminRoute>
          }
        >
          <Route index element={<Navigate to="/admin/workspaces" replace />} />
          <Route path="workspaces" element={<WorkspacesPage />} />
          <Route path="models" element={<ModelsPage />} />
          <Route path="users" element={<UsersPage />} />
          <Route path="backups" element={<BackupPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;

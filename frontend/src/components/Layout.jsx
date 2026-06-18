import { useMemo, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useChats } from '../context/ChatContext';
import { useWorkspaces } from '../context/WorkspaceContext';
import { formatChatDate } from '../utils/chat';
import SettingsIcon from './icons/SettingsIcon';
import ProfileIcon from './icons/ProfileIcon';

function workspaceIsActive(location, workspaceId, chats) {
  const path = location.pathname;
  if (path === `/workspace/${workspaceId}`) {
    return true;
  }
  const match = path.match(/^\/chat\/(\d+)$/);
  if (!match) {
    return false;
  }
  const chat = chats.find((item) => String(item.id) === match[1]);
  return chat && String(chat.workspace) === String(workspaceId);
}

function Layout() {
  const { user, isAdmin } = useAuth();
  const { chats, loading: chatsLoading } = useChats();
  const { workspaces, loading: workspacesLoading } = useWorkspaces();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const isAdminSection = location.pathname.startsWith('/admin');
  const isProfileSection = location.pathname.startsWith('/profile');

  const closeMenu = () => setMenuOpen(false);

  const chatsByWorkspace = useMemo(() => {
    const map = new Map();
    workspaces.forEach((workspace) => {
      map.set(workspace.id, []);
    });
    chats.forEach((chat) => {
      if (chat.workspace && map.has(chat.workspace)) {
        map.get(chat.workspace).push(chat);
      }
    });
    return map;
  }, [chats, workspaces]);

  const orphanChats = useMemo(
    () => (isAdmin ? chats.filter((chat) => !chat.workspace) : []),
    [chats, isAdmin],
  );

  const showWorkspaceNav = !isAdmin && workspaces.length > 0;

  return (
    <div className="layout">
      <header className="header">
        <div className="header__inner">
          <button
            type="button"
            className="header__menu-btn"
            aria-label="Відкрити меню"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen(!menuOpen)}
          >
            <span />
            <span />
            <span />
          </button>

          <h1 className="header__logo">ZROZUMILOAI</h1>

          <div className="header__user">
            <span className="header__username">{user?.username}</span>
            <NavLink
              to="/profile"
              className={`header__profile-btn${isProfileSection ? ' header__profile-btn--active' : ''}`}
              aria-label="Налаштування профілю"
              title="Налаштування профілю"
            >
              <ProfileIcon />
            </NavLink>
          </div>
        </div>
      </header>

      <div className="layout__body">
        <nav
          className={`sidebar ${menuOpen ? 'sidebar--open' : ''}`}
          aria-label="Головна навігація"
        >
          <ul className="sidebar__nav sidebar__nav--scroll">
            {isAdmin && (
              <li>
                <NavLink to="/" end className="sidebar__link" onClick={closeMenu}>
                  Новий чат
                </NavLink>
              </li>
            )}

            {showWorkspaceNav && workspaces.map((workspace) => {
              const workspaceChats = chatsByWorkspace.get(workspace.id) || [];
              const isActive = workspaceIsActive(location, workspace.id, chats);

              return (
                <li key={workspace.id} className="sidebar__workspace-group">
                  <NavLink
                    to={`/workspace/${workspace.id}`}
                    className={`sidebar__workspace-link${isActive ? ' active' : ''}`}
                    onClick={closeMenu}
                    title={workspace.model_names?.join(', ') || ''}
                  >
                    <span className="sidebar__workspace-name">{workspace.name}</span>
                    {workspace.model_names?.length > 0 && (
                      <span className="sidebar__workspace-model">
                        {workspace.model_names.join(', ')}
                      </span>
                    )}
                  </NavLink>
                  {workspaceChats.map((chat) => (
                    <NavLink
                      key={chat.id}
                      to={`/chat/${chat.id}`}
                      className="sidebar__chat-link sidebar__chat-link--nested"
                      onClick={closeMenu}
                      title={chat.title}
                    >
                      <span className="sidebar__chat-title">{chat.title}</span>
                      <span className="sidebar__chat-meta">
                        {formatChatDate(chat.updated_at)}
                      </span>
                    </NavLink>
                  ))}
                </li>
              );
            })}

            {!isAdmin && !workspacesLoading && workspaces.length === 0 && (
              <li className="sidebar__empty">Немає призначених workspace</li>
            )}

            {isAdmin && workspaces.length > 0 && (
              <>
                <li className="sidebar__section" aria-hidden="true">
                  Workspaces
                </li>
                {workspaces.map((workspace) => {
                  const workspaceChats = chatsByWorkspace.get(workspace.id) || [];
                  const isActive = workspaceIsActive(location, workspace.id, chats);

                  return (
                    <li key={workspace.id} className="sidebar__workspace-group">
                      <NavLink
                        to={`/workspace/${workspace.id}`}
                        className={`sidebar__workspace-link${isActive ? ' active' : ''}`}
                        onClick={closeMenu}
                      >
                        <span className="sidebar__workspace-name">{workspace.name}</span>
                      </NavLink>
                      {workspaceChats.map((chat) => (
                        <NavLink
                          key={chat.id}
                          to={`/chat/${chat.id}`}
                          className="sidebar__chat-link sidebar__chat-link--nested"
                          onClick={closeMenu}
                          title={chat.title}
                        >
                          <span className="sidebar__chat-title">{chat.title}</span>
                          <span className="sidebar__chat-meta">
                            {formatChatDate(chat.updated_at)}
                          </span>
                        </NavLink>
                      ))}
                    </li>
                  );
                })}
              </>
            )}

            {isAdmin && orphanChats.length > 0 && (
              <>
                <li className="sidebar__section" aria-hidden="true">
                  Без workspace
                </li>
                {orphanChats.map((chat) => (
                  <li key={chat.id}>
                    <NavLink
                      to={`/chat/${chat.id}`}
                      className="sidebar__chat-link"
                      onClick={closeMenu}
                      title={chat.title}
                    >
                      <span className="sidebar__chat-title">{chat.title}</span>
                      <span className="sidebar__chat-meta">
                        {formatChatDate(chat.updated_at)}
                      </span>
                    </NavLink>
                  </li>
                ))}
              </>
            )}

            {isAdmin && chats.length > 0 && workspaces.length === 0 && orphanChats.length === 0 && (
              <>
                <li className="sidebar__section" aria-hidden="true">
                  Збережені чати
                </li>
                {chats.map((chat) => (
                  <li key={chat.id}>
                    <NavLink
                      to={`/chat/${chat.id}`}
                      className="sidebar__chat-link"
                      onClick={closeMenu}
                      title={chat.title}
                    >
                      <span className="sidebar__chat-title">{chat.title}</span>
                      <span className="sidebar__chat-meta">
                        {formatChatDate(chat.updated_at)}
                      </span>
                    </NavLink>
                  </li>
                ))}
              </>
            )}

            {(chatsLoading || workspacesLoading) && chats.length === 0 && (
              <li className="sidebar__chat-loading">Завантаження…</li>
            )}
          </ul>

          {isAdmin && (
            <div className="sidebar__footer">
              <NavLink
                to="/admin"
                className={`sidebar__admin-btn${isAdminSection ? ' sidebar__admin-btn--active' : ''}`}
                onClick={closeMenu}
                aria-label="Адміністрування"
                title="Адміністрування"
              >
                <SettingsIcon />
                <span>Адміністрування</span>
              </NavLink>
            </div>
          )}
        </nav>

        {menuOpen && (
          <button
            type="button"
            className="sidebar-overlay"
            aria-label="Закрити меню"
            onClick={closeMenu}
          />
        )}

        <main className="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default Layout;

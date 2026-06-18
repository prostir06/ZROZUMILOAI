import { NavLink, Outlet } from 'react-router-dom';

const ADMIN_LINKS = [
  { to: '/admin/workspaces', label: 'Workspaces' },
  { to: '/admin/models', label: 'Моделі' },
  { to: '/admin/users', label: 'Користувачі' },
  { to: '/admin/backups', label: 'Backup' },
];

function AdminLayout() {
  return (
    <div className="admin-shell">
      <aside className="admin-shell__nav" aria-label="Адміністрування">
        <h2 className="admin-shell__title">Адміністрування</h2>
        <ul className="admin-shell__links">
          {ADMIN_LINKS.map((link) => (
            <li key={link.to}>
              <NavLink
                to={link.to}
                className={({ isActive }) =>
                  `admin-shell__link${isActive ? ' admin-shell__link--active' : ''}`
                }
              >
                {link.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </aside>
      <div className="admin-shell__content">
        <Outlet />
      </div>
    </div>
  );
}

export default AdminLayout;

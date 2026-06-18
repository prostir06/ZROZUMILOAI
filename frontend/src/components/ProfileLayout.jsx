import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const PROFILE_LINKS = [
  { to: '/profile/appearance', label: 'Оформлення' },
  { to: '/profile/password', label: 'Пароль' },
];

function ProfileLayout() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="admin-shell">
      <aside className="admin-shell__nav" aria-label="Налаштування профілю">
        <h2 className="admin-shell__title">Профіль</h2>
        <ul className="admin-shell__links">
          {PROFILE_LINKS.map((link) => (
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
        <button
          type="button"
          className="btn btn--ghost admin-shell__logout"
          onClick={handleLogout}
        >
          Вийти
        </button>
      </aside>
      <div className="admin-shell__content">
        <Outlet />
      </div>
    </div>
  );
}

export default ProfileLayout;

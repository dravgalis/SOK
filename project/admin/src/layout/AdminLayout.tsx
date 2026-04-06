import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { clearAdminToken } from '../auth';

const navItems = [
  { to: '/admin', label: 'Dashboard', end: true },
  { to: '/admin/vacancies', label: 'Vacancies' },
  { to: '/admin/candidates', label: 'Candidates' },
  { to: '/admin/settings', label: 'Settings' },
];

export function AdminLayout() {
  const navigate = useNavigate();

  function handleLogout() {
    clearAdminToken();
    navigate('/', { replace: true });
  }

  return (
    <div className="admin-layout">
      <aside className="sidebar">
        <div className="brand">Admin Panel</div>
        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                isActive ? 'sidebar-link sidebar-link-active' : 'sidebar-link'
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <button className="logout-button" onClick={handleLogout} type="button">
          Выйти
        </button>
      </aside>

      <main className="admin-content">
        <Outlet />
      </main>
    </div>
  );
}

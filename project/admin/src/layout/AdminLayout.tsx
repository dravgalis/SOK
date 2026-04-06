import { NavLink, Outlet } from 'react-router-dom';

const navItems = [
  { to: '/admin', label: 'Dashboard', end: true },
  { to: '/admin/vacancies', label: 'Vacancies' },
  { to: '/admin/candidates', label: 'Candidates' },
  { to: '/admin/settings', label: 'Settings' },
];

export function AdminLayout() {
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
      </aside>

      <main className="admin-content">
        <Outlet />
      </main>
    </div>
  );
}

import { NavLink, Outlet } from 'react-router-dom';
import './AppShell.css';

const links = [
  { to: '/', label: 'Reports', end: true },
  { to: '/map', label: 'Map' },
  { to: '/track', label: 'Track' },
  { to: '/privacy', label: 'Privacy' },
  { to: '/login', label: 'Sign in' },
];

export function AppShell() {
  return (
    <div className="shell">
      <header className="shell-header">
        <div className="shell-brand">
          <span className="shell-mark" aria-hidden>
            BG
          </span>
          <div>
            <p className="shell-title">BaladiGuard</p>
            <p className="shell-subtitle">Citizen reports</p>
          </div>
        </div>
        <nav className="shell-nav" aria-label="Main">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) =>
                isActive ? 'shell-nav-link shell-nav-link-active' : 'shell-nav-link'
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="shell-main">
        <Outlet />
      </main>
      <footer className="shell-footer">
        <NavLink to="/report">Submit a report</NavLink>
        <NavLink to="/history">My history</NavLink>
        <NavLink to="/profile">Profile</NavLink>
      </footer>
    </div>
  );
}

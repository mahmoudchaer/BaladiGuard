import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useCitizenAuth } from '@/auth/CitizenAuthContext';
import './AppShell.css';

const publicLinks = [
  { to: '/', label: 'Home', end: true },
  { to: '/reports', label: 'Explore' },
];

export function AppShell() {
  const auth = useCitizenAuth();
  const navigate = useNavigate();
  const links = auth.isAuthenticated
    ? [
        { to: '/', label: 'Home', end: true },
        { to: '/history', label: 'My reports' },
        { to: '/report', label: 'New report' },
      ]
    : publicLinks;
  return (
    <div className="shell">
      <header className="shell-header">
        <NavLink className="shell-brand" to="/" aria-label="BaladiGuard home">
          <span className="shell-mark" aria-hidden>
            <span>⌖</span>
          </span>
          <div>
            <p className="shell-title">BaladiGuard</p>
            <p className="shell-subtitle">Citizen reports</p>
          </div>
        </NavLink>
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
          {auth.isAuthenticated ? (
            <button
              className="nav-avatar tactile"
              aria-label="Open profile"
              onClick={() => navigate('/profile')}
            >
              {auth.profile?.fullName?.[0]?.toUpperCase() || 'B'}
            </button>
          ) : (
            <NavLink className="button nav-sign-in" to="/login">
              Sign in
            </NavLink>
          )}
        </nav>
      </header>
      <main className="shell-main">
        <Outlet />
      </main>
      <footer className="shell-footer">
        <div className="footer-brand">
          <span className="shell-mark" aria-hidden>
            ⌖
          </span>
          <div>
            <strong>BaladiGuard</strong>
            <p>Built for clearer, safer civic reporting.</p>
          </div>
        </div>
        <div className="footer-links">
          <div>
            <strong>Platform</strong>
            <NavLink to="/reports">Public reports</NavLink>
            <NavLink to="/map">Report map</NavLink>
          </div>
          <div>
            <strong>Take action</strong>
            <NavLink to="/report">Report an issue</NavLink>
            <NavLink to="/track">Track with a code</NavLink>
          </div>
          <div>
            <strong>About</strong>
            <NavLink to="/privacy">Privacy</NavLink>
            <NavLink to={auth.isAuthenticated ? '/profile' : '/login'}>
              {auth.isAuthenticated ? 'Your profile' : 'Citizen sign in'}
            </NavLink>
          </div>
        </div>
        <div className="footer-bottom">
          <span>© {new Date().getFullYear()} BaladiGuard</span>
          <span>Verified-phone accounts · Privacy-safe public data</span>
        </div>
      </footer>
    </div>
  );
}

import type { ReactNode } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useStaffAuth } from '@/auth/useStaffAuth';
import { config } from '@/services/config';
import { IconAnalytics, IconMap, IconTickets } from '@/components/icons';
import './DashboardLayout.css';

type DashboardLayoutProps = {
  children: ReactNode;
  title?: string;
  subtitle?: string;
};

type NavItem =
  | {
      id: string;
      label: string;
      Icon: typeof IconTickets;
      to: string;
      soon?: false;
    }
  | {
      id: string;
      label: string;
      Icon: typeof IconTickets;
      soon: true;
    };

const NAV_ITEMS: NavItem[] = [
  { id: 'tickets', label: 'Tickets', Icon: IconTickets, to: '/' },
  { id: 'map', label: 'Map View', Icon: IconMap, to: '/map' },
  { id: 'analytics', label: 'Analytics', Icon: IconAnalytics, soon: true },
];

function isNavActive(pathname: string, to: string): boolean {
  if (to === '/') {
    return pathname === '/' || pathname.startsWith('/tickets');
  }
  return pathname === to || pathname.startsWith(`${to}/`);
}

export function DashboardLayout({
  children,
  title = 'Ticket Dashboard',
  subtitle = 'Monitor and manage citizen infrastructure reports',
}: DashboardLayoutProps) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { logout, session } = useStaffAuth();

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className="dashboard-layout">
      <aside className="dashboard-sidebar">
        <div className="dashboard-sidebar__flag" aria-hidden="true" />
        <div className="dashboard-sidebar__brand">
          <span className="dashboard-sidebar__logo" aria-hidden="true">
            BG
          </span>
          <div>
            <p className="dashboard-sidebar__name">BaladiGuard</p>
            <p className="dashboard-sidebar__role">Municipal Staff Portal</p>
          </div>
        </div>

        <nav className="dashboard-sidebar__nav" aria-label="Main navigation">
          {NAV_ITEMS.map((item) => {
            if (item.soon) {
              return (
                <span
                  key={item.id}
                  className="dashboard-sidebar__link dashboard-sidebar__link--disabled"
                >
                  <span className="dashboard-sidebar__link-icon" aria-hidden="true">
                    <item.Icon />
                  </span>
                  {item.label}
                  <span className="dashboard-sidebar__soon">Soon</span>
                </span>
              );
            }

            const active = isNavActive(pathname, item.to);

            return (
              <NavLink
                key={item.id}
                to={item.to}
                end={item.to === '/'}
                className={`dashboard-sidebar__link${
                  active ? ' dashboard-sidebar__link--active' : ''
                }`}
                aria-current={active ? 'page' : undefined}
              >
                <span className="dashboard-sidebar__link-icon" aria-hidden="true">
                  <item.Icon />
                </span>
                {item.label}
              </NavLink>
            );
          })}
        </nav>

        <div className="dashboard-sidebar__footer">
          <div className="dashboard-sidebar__staff">
            <span className="dashboard-sidebar__avatar" aria-hidden="true">
              {session?.username.slice(0, 2).toUpperCase() ?? 'MS'}
            </span>
            <div>
              <p className="dashboard-sidebar__staff-name">{session?.username ?? 'Staff'}</p>
              <p className="dashboard-sidebar__staff-role">Administrator</p>
            </div>
          </div>
        </div>
      </aside>

      <div className="dashboard-shell">
        <header className="dashboard-topbar">
          <div className="dashboard-topbar__flag" aria-hidden="true" />
          <div className="dashboard-topbar__left">
            <h1 className="dashboard-topbar__title">{title}</h1>
            <p className="dashboard-topbar__subtitle">{subtitle}</p>
          </div>
          <div className="dashboard-topbar__actions">
            {config.useMockData && <span className="dashboard-topbar__badge">Mock data mode</span>}
            <span className="dashboard-topbar__date">
              {new Intl.DateTimeFormat(undefined, {
                weekday: 'long',
                month: 'long',
                day: 'numeric',
              }).format(new Date())}
            </span>
            <button className="dashboard-topbar__logout" type="button" onClick={handleLogout}>
              Logout
            </button>
          </div>
        </header>

        <main className="dashboard-main">{children}</main>
      </div>
    </div>
  );
}

import type { ReactNode } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useStaffAuth } from '@/auth/useStaffAuth';
import { config } from '@/services/config';
import { getStaffRoleLabel } from '@/services/auth';
import { BrandMark } from '@/components/BrandMark';
import { IconMap, IconSearch, IconTickets } from '@/components/icons';
import './BrandMark.css';
import './DashboardLayout.css';

type DashboardLayoutProps = {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  /** When true, main content is flush for multi-pane desk layouts. */
  flush?: boolean;
  search?: {
    value: string;
    onChange: (value: string) => void;
    label?: string;
    placeholder?: string;
  };
};

type NavItem = {
  id: string;
  label: string;
  Icon: typeof IconTickets;
  to: string;
};

/** Analytics stays off the nav until a dedicated page exists; queue insights remain secondary on Tickets. */
const NAV_ITEMS: NavItem[] = [
  { id: 'tickets', label: 'Tickets', Icon: IconTickets, to: '/' },
  { id: 'map', label: 'Map View', Icon: IconMap, to: '/map' },
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
  flush = false,
  search,
}: DashboardLayoutProps) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { logout, session } = useStaffAuth();
  const searchLabel = search?.label ?? 'Search tickets';
  const searchId = 'dashboard-global-search';

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className={`dashboard-layout${flush ? ' dashboard-layout--flush' : ''}`}>
      <aside className="dashboard-rail" aria-label="Primary modules">
        <NavLink to="/" className="dashboard-rail__brand" aria-label="BaladiGuard home">
          <BrandMark size={22} />
        </NavLink>

        <nav className="dashboard-rail__nav" aria-label="Main navigation">
          {NAV_ITEMS.map((item) => {
            const active = isNavActive(pathname, item.to);
            return (
              <NavLink
                key={item.id}
                to={item.to}
                end={item.to === '/'}
                className={`dashboard-rail__link${active ? ' dashboard-rail__link--active' : ''}`}
                aria-current={active ? 'page' : undefined}
                title={item.label}
              >
                <item.Icon />
                <span className="dashboard-rail__link-label">{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </aside>

      <div className="dashboard-shell">
        <header className="dashboard-topbar">
          <div className="dashboard-topbar__brand-block">
            <p className="dashboard-topbar__product">BaladiGuard</p>
            <p className="dashboard-topbar__context">Municipal desk</p>
          </div>

          {search ? (
            <div className="dashboard-topbar__search">
              <label className="sr-only" htmlFor={searchId}>
                {searchLabel}
              </label>
              <span className="dashboard-topbar__search-icon" aria-hidden="true">
                <IconSearch />
              </span>
              <input
                id={searchId}
                type="search"
                className="dashboard-topbar__search-input"
                value={search.value}
                onChange={(event) => search.onChange(event.target.value)}
                placeholder={search.placeholder ?? 'Search Capacity…'}
                autoComplete="off"
              />
            </div>
          ) : (
            <div className="dashboard-topbar__titles">
              <h1 className="dashboard-topbar__title">{title}</h1>
              {subtitle ? <p className="dashboard-topbar__subtitle">{subtitle}</p> : null}
            </div>
          )}

          <div className="dashboard-topbar__actions">
            {config.useMockData && <span className="dashboard-topbar__badge">Mock data</span>}
            <span className="dashboard-topbar__date">
              {new Intl.DateTimeFormat(undefined, {
                weekday: 'short',
                month: 'short',
                day: 'numeric',
              }).format(new Date())}
            </span>
            <div className="dashboard-topbar__staff" title={getStaffRoleLabel(session?.role)}>
              <span className="dashboard-topbar__avatar" aria-hidden="true">
                {(session?.name ?? session?.username ?? 'MS').slice(0, 2).toUpperCase()}
              </span>
              <span className="dashboard-topbar__staff-name">
                {session?.name ?? session?.username ?? 'Staff'}
              </span>
            </div>
            <button className="dashboard-topbar__logout" type="button" onClick={handleLogout}>
              Logout
            </button>
          </div>
        </header>

        {/* Keep page title available for screen readers / tests when search occupies the topbar. */}
        {search ? <h1 className="sr-only">{title}</h1> : null}

        <main className={`dashboard-main${flush ? ' dashboard-main--flush' : ''}`}>{children}</main>
      </div>
    </div>
  );
}

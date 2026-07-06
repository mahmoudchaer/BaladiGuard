import type { ReactNode } from 'react';
import { config } from '@/services/config';
import { IconAnalytics, IconMap, IconTickets } from '@/components/icons';
import './DashboardLayout.css';

type DashboardLayoutProps = {
  children: ReactNode;
  title?: string;
  subtitle?: string;
};

const NAV_ITEMS = [
  { id: 'tickets', label: 'Tickets', Icon: IconTickets, active: true },
  { id: 'map', label: 'Map View', Icon: IconMap, active: false, soon: true },
  { id: 'analytics', label: 'Analytics', Icon: IconAnalytics, active: false, soon: true },
] as const;

export function DashboardLayout({
  children,
  title = 'Ticket Dashboard',
  subtitle = 'Monitor and manage citizen infrastructure reports',
}: DashboardLayoutProps) {
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
          {NAV_ITEMS.map((item) => (
            <span
              key={item.id}
              className={`dashboard-sidebar__link${
                item.active ? ' dashboard-sidebar__link--active' : ''
              }${'soon' in item && item.soon ? ' dashboard-sidebar__link--disabled' : ''}`}
              aria-current={item.active ? 'page' : undefined}
            >
              <span className="dashboard-sidebar__link-icon" aria-hidden="true">
                <item.Icon />
              </span>
              {item.label}
              {'soon' in item && item.soon && <span className="dashboard-sidebar__soon">Soon</span>}
            </span>
          ))}
        </nav>

        <div className="dashboard-sidebar__footer">
          <div className="dashboard-sidebar__staff">
            <span className="dashboard-sidebar__avatar" aria-hidden="true">
              MS
            </span>
            <div>
              <p className="dashboard-sidebar__staff-name">Municipality Staff</p>
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
          </div>
        </header>

        <main className="dashboard-main">{children}</main>
      </div>
    </div>
  );
}

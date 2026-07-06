import type { ReactNode } from 'react';
import { config } from '@/services/config';
import './DashboardLayout.css';

type DashboardLayoutProps = {
  children: ReactNode;
};

const NAV_ITEMS = [
  { id: 'tickets', label: 'Tickets', icon: '📋', active: true },
  { id: 'map', label: 'Map View', icon: '🗺️', active: false, soon: true },
  { id: 'analytics', label: 'Analytics', icon: '📊', active: false, soon: true },
];

export function DashboardLayout({ children }: DashboardLayoutProps) {
  return (
    <div className="dashboard-layout">
      <aside className="dashboard-sidebar">
        <div className="dashboard-sidebar__brand">
          <span className="dashboard-sidebar__logo" aria-hidden="true">
            BG
          </span>
          <div>
            <p className="dashboard-sidebar__name">BaladiGuard</p>
            <p className="dashboard-sidebar__role">Staff Portal</p>
          </div>
        </div>

        <nav className="dashboard-sidebar__nav" aria-label="Main navigation">
          {NAV_ITEMS.map((item) => (
            <span
              key={item.id}
              className={`dashboard-sidebar__link${
                item.active ? ' dashboard-sidebar__link--active' : ''
              }${item.soon ? ' dashboard-sidebar__link--disabled' : ''}`}
              aria-current={item.active ? 'page' : undefined}
            >
              <span className="dashboard-sidebar__link-icon" aria-hidden="true">
                {item.icon}
              </span>
              {item.label}
              {item.soon && <span className="dashboard-sidebar__soon">Soon</span>}
            </span>
          ))}
        </nav>

        <div className="dashboard-sidebar__footer">
          <div className="dashboard-sidebar__staff">
            <span className="dashboard-sidebar__avatar" aria-hidden="true">
              M
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
          <div className="dashboard-topbar__left">
            <h1 className="dashboard-topbar__title">Ticket Dashboard</h1>
            <p className="dashboard-topbar__subtitle">
              Monitor and manage citizen infrastructure reports
            </p>
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

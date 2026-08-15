import { useState, type ReactNode } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useStaffAuth } from '@/auth/useStaffAuth';
import { config } from '@/services/config';
import { getStaffRoleLabel } from '@/services/auth';
import { BrandMark } from '@/components/BrandMark';
import { GlobalSearch } from '@/components/GlobalSearch';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { StaffAssistantPanel } from '@/components/StaffAssistantPanel';
import { useI18n } from '@/i18n/LocaleProvider';
import { IconMap, IconPeople, IconSparkles, IconTickets } from '@/components/icons';
import './BrandMark.css';
import './DashboardLayout.css';

type DashboardLayoutProps = {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  /** When true, main content is flush for multi-pane desk layouts. */
  flush?: boolean;
};

type NavItem = {
  id: string;
  label: string;
  Icon: typeof IconTickets;
  to: string;
};

/** Analytics stays off the nav until a dedicated page exists; queue insights remain secondary on Tickets. */
const NAV_ITEM_DEFS: Array<Omit<NavItem, 'label'> & { labelKey: string }> = [
  { id: 'tickets', labelKey: 'nav.tickets', Icon: IconTickets, to: '/' },
  { id: 'map', labelKey: 'nav.map', Icon: IconMap, to: '/map' },
  { id: 'workforce', labelKey: 'nav.workforce', Icon: IconPeople, to: '/workforce' },
];

function isNavActive(pathname: string, to: string): boolean {
  if (to === '/') {
    return pathname === '/' || pathname.startsWith('/tickets');
  }
  return pathname === to || pathname.startsWith(`${to}/`);
}

export function DashboardLayout({
  children,
  title,
  subtitle,
  flush = false,
}: DashboardLayoutProps) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { logout, session } = useStaffAuth();
  const { t } = useI18n();
  const [assistantOpen, setAssistantOpen] = useState(false);
  const resolvedTitle = title ?? t('layout.title');
  const resolvedSubtitle = subtitle ?? t('layout.subtitle');
  const navItems = NAV_ITEM_DEFS.map((item) => ({ ...item, label: t(item.labelKey) }));

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className={`dashboard-layout${flush ? ' dashboard-layout--flush' : ''}`}>
      <aside className="dashboard-rail" aria-label={t('nav.primaryModules')} inert={assistantOpen}>
        <NavLink to="/" className="dashboard-rail__brand" aria-label={t('nav.home')}>
          <BrandMark size={22} />
        </NavLink>

        <nav className="dashboard-rail__nav" aria-label={t('nav.mainNav')}>
          {navItems.map((item) => {
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

      <div className="dashboard-shell" inert={assistantOpen}>
        <header className="dashboard-topbar">
          <div className="dashboard-topbar__brand-block">
            <p className="dashboard-topbar__product">{t('topbar.product')}</p>
            <p className="dashboard-topbar__context">{t('topbar.context')}</p>
          </div>

          <GlobalSearch />

          <div className="dashboard-topbar__actions">
            <button
              type="button"
              className="dashboard-topbar__assistant"
              aria-expanded={assistantOpen}
              aria-controls="staff-assistant-panel"
              onClick={() => setAssistantOpen(true)}
            >
              <IconSparkles />
              {t('topbar.assistant')}
            </button>
            {config.useMockData && (
              <span className="dashboard-topbar__badge">{t('topbar.mockData')}</span>
            )}
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
            <LanguageSwitcher compact />
            <button className="dashboard-topbar__logout" type="button" onClick={handleLogout}>
              {t('topbar.logout')}
            </button>
          </div>
        </header>

        <h1 className="sr-only">{resolvedTitle}</h1>
        {resolvedSubtitle ? <p className="sr-only">{resolvedSubtitle}</p> : null}

        <main className={`dashboard-main${flush ? ' dashboard-main--flush' : ''}`}>{children}</main>
      </div>

      <StaffAssistantPanel open={assistantOpen} onClose={() => setAssistantOpen(false)} />
    </div>
  );
}

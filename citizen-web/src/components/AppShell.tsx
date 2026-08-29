import { useEffect, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useCitizenAuth } from '@/auth/CitizenAuthContext';
import { BrandMark } from '@/components/BrandMark';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { ProfileAvatarContent } from '@/components/ProfileAvatarContent';
import { useI18n } from '@/i18n/LocaleProvider';
import './AppShell.css';

const COMPACT_NAV_PX = 768;

export function AppShell() {
  const auth = useCitizenAuth();
  const navigate = useNavigate();
  const { t } = useI18n();
  const [compact, setCompact] = useState(
    () => typeof window !== 'undefined' && window.innerWidth < COMPACT_NAV_PX,
  );
  const [menuOpen, setMenuOpen] = useState(
    () => typeof window === 'undefined' || window.innerWidth >= COMPACT_NAV_PX,
  );

  useEffect(() => {
    const onResize = () => {
      const nextCompact = window.innerWidth < COMPACT_NAV_PX;
      setCompact(nextCompact);
      if (!nextCompact) setMenuOpen(true);
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const links = auth.isAuthenticated
    ? [
        { to: '/', label: t('shell.home'), end: true },
        { to: '/history', label: t('shell.myReports'), end: false },
        { to: '/rewards', label: t('shell.rewards'), end: false },
        { to: '/leaderboard', label: t('shell.leaderboard'), end: false },
        { to: '/report', label: t('shell.newReport'), end: false },
        { to: '/reports', label: t('shell.explore'), end: false },
      ]
    : [
        { to: '/', label: t('shell.home'), end: true },
        { to: '/reports', label: t('shell.explore'), end: false },
        { to: '/leaderboard', label: t('shell.leaderboard'), end: false },
        { to: '/track', label: t('shell.trackCode'), end: false },
      ];
  const navHidden = compact && !menuOpen;

  return (
    <div className="shell">
      <div className="shell-stripe" aria-hidden />
      <header className="shell-header">
        <NavLink className="shell-brand" to="/" aria-label={t('shell.homeAria')}>
          <span className="shell-mark" aria-hidden>
            <BrandMark size={40} />
          </span>
          <div>
            <p className="shell-title">BaladiGuard</p>
            <p className="shell-subtitle">{t('shell.subtitle')}</p>
          </div>
        </NavLink>
        <nav className="shell-nav" aria-label={t('shell.mainNav')}>
          <button
            type="button"
            className="nav-menu-toggle tactile"
            aria-expanded={menuOpen}
            aria-controls="shell-nav-links"
            onClick={() => setMenuOpen((open) => !open)}
          >
            {menuOpen ? t('common.closeMenu') : t('common.openMenu')}
          </button>
          <div id="shell-nav-links" className="shell-nav-links" hidden={navHidden}>
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  isActive ? 'shell-nav-link shell-nav-link-active' : 'shell-nav-link'
                }
                onClick={() => {
                  if (compact) setMenuOpen(false);
                }}
              >
                {link.label}
              </NavLink>
            ))}
          </div>
          {auth.isAuthenticated ? (
            <button
              className="nav-avatar tactile"
              aria-label={t('shell.openProfile')}
              onClick={() => navigate('/profile')}
            >
              <ProfileAvatarContent fullName={auth.profile?.fullName} />
            </button>
          ) : (
            <NavLink className="button nav-sign-in" to="/login">
              {t('common.signIn')}
            </NavLink>
          )}
          <LanguageSwitcher compact />
        </nav>
      </header>
      <main id="main-content" className="shell-main" tabIndex={-1}>
        <Outlet />
      </main>
      <footer className="shell-footer">
        <div className="footer-brand">
          <span className="shell-mark" aria-hidden>
            <BrandMark size={40} />
          </span>
          <div>
            <strong>BaladiGuard</strong>
            <p>{t('shell.footerTagline')}</p>
          </div>
        </div>
        <div className="footer-links">
          <div>
            <strong>{t('shell.platform')}</strong>
            <NavLink to="/reports">{t('shell.publicReports')}</NavLink>
            <NavLink to="/map">{t('shell.reportMap')}</NavLink>
          </div>
          <div>
            <strong>{t('shell.takeAction')}</strong>
            <NavLink to="/report">{t('shell.reportIssue')}</NavLink>
            <NavLink to="/track">{t('shell.trackCode')}</NavLink>
          </div>
          <div>
            <strong>{t('shell.about')}</strong>
            <NavLink to="/privacy">{t('shell.privacy')}</NavLink>
            <NavLink to="/terms">{t('shell.terms')}</NavLink>
            <NavLink to="/acceptable-use">{t('shell.acceptableUse')}</NavLink>
            <NavLink to={auth.isAuthenticated ? '/profile' : '/login'}>
              {auth.isAuthenticated ? t('shell.yourProfile') : t('shell.citizenSignIn')}
            </NavLink>
          </div>
        </div>
        <div className="footer-bottom">
          <span>© {new Date().getFullYear()} BaladiGuard</span>
          <span>{t('shell.footerLegal')}</span>
        </div>
      </footer>
    </div>
  );
}

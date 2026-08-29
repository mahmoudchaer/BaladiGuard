import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useCitizenAuth } from '@/auth/CitizenAuthContext';
import { StatusChip } from '@/components/StatusChip';
import { CivicIllustration } from '@/components/CivicIllustration';
import { translateCategory } from '@/i18n';
import { useI18n } from '@/i18n/LocaleProvider';
import { getHistory } from '@/services/contributions';
import type { CitizenTicketHistoryItem } from '@/types/ticket';

export function HomePage() {
  const auth = useCitizenAuth();
  if (auth.isAuthenticated) return <CitizenHome />;
  return <PublicHome />;
}

function greetingEyebrow(t: (key: string) => string): string {
  const hour = new Date().getHours();
  if (hour < 12) return t('home.morning');
  if (hour < 18) return t('home.afternoon');
  return t('home.evening');
}

function CitizenHome() {
  const { t } = useI18n();
  const { profile } = useCitizenAuth();
  const [reports, setReports] = useState<CitizenTicketHistoryItem[]>([]);
  const [error, setError] = useState(false);
  const load = useCallback(() => {
    setError(false);
    void getHistory(3)
      .then((page) => setReports(page.items))
      .catch(() => setError(true));
  }, []);
  useEffect(() => {
    load();
  }, [load]);
  const firstName = profile?.fullName?.trim().split(/\s+/)[0];
  const active = reports.filter((item) => !['RESOLVED', 'CLOSED'].includes(item.status)).length;
  return (
    <section className="citizen-home page-enter">
      <div className="home-welcome">
        <div>
          <span className="eyebrow">{greetingEyebrow(t)}</span>
          <h1>{firstName ? t('home.helloName', { name: firstName }) : t('home.hello')}</h1>
          <p className="lede">{t('home.citizenLede')}</p>
        </div>
      </div>
      <Link className="primary-action tactile" to="/report">
        <span className="action-icon">＋</span>
        <span>
          <strong>{t('home.reportIssue')}</strong>
          <small>{t('home.reportHint')}</small>
        </span>
        <span aria-hidden>→</span>
      </Link>
      <div className="quick-grid">
        <Link className="quick-card tactile" to="/track">
          <span>▦</span>
          <strong>{t('home.trackCode')}</strong>
          <small>{t('home.trackHint')}</small>
        </Link>
        <Link className="quick-card tactile" to="/map">
          <span aria-hidden>⌖</span>
          <strong>{t('home.nearby')}</strong>
          <small>{t('home.browseReports')}</small>
        </Link>
      </div>
      <div className="section-heading">
        <div>
          <h2>{t('home.yourReports')}</h2>
          <span>
            {reports.length ? t('home.activeCount', { count: active }) : t('home.yourActivity')}
          </span>
        </div>
        <Link to="/history">{t('home.viewAll')}</Link>
      </div>
      {error ? (
        <div className="notice notice-info">
          <p>{t('home.refreshFailed')}</p>
          <button type="button" className="text-button" onClick={load}>
            {t('common.retry')}
          </button>
        </div>
      ) : null}
      {!error && reports.length === 0 ? (
        <div className="empty-state compact">
          <CivicIllustration name="report-clipboard" className="civic-illustration--empty" />
          <h2>{t('home.emptyTitle')}</h2>
          <p>{t('home.emptyBody')}</p>
        </div>
      ) : null}
      {reports.length ? (
        <div className="history-list">
          {reports.map((report) => (
            <Link
              className="history-row tactile"
              key={report.trackingCode}
              to={`/track?trackingCode=${report.trackingCode}`}
            >
              <span className="history-glyph" aria-hidden>
                ⌖
              </span>
              <div className="history-copy">
                <strong>{translateCategory(report.category)}</strong>
                <span>{report.locationAddress}</span>
              </div>
              <StatusChip status={report.status} />
              <span>›</span>
            </Link>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function PublicHome() {
  const { t } = useI18n();
  return (
    <div className="landing-page page-enter">
      <div className="public-hero">
        <div>
          <p className="hero-welcome">{t('home.welcome')}</p>
          <h1>
            {t('home.heroLine1')}
            <br />
            {t('home.heroLine2')}
          </h1>
          <p className="lede">{t('home.publicLede')}</p>
          <div className="button-row home-auth-actions">
            <Link className="button button-large" to="/report">
              {t('home.reportCta')}
            </Link>
            <Link className="button button-secondary button-large" to="/reports">
              {t('home.continueGuest')}
            </Link>
          </div>
          <p className="helper">{t('home.phoneHint')}</p>
        </div>
        <div className="hero-symbol" aria-hidden>
          <CivicIllustration
            name="citizen-reporting"
            className="civic-illustration--hero"
            priority
          />
          <span>
            <i /> {t('home.builtFor')}
          </span>
        </div>
      </div>
      <section className="landing-features" aria-label={t('home.howItWorks')}>
        <div>
          <span>01</span>
          <h2>{t('home.reportClearly')}</h2>
          <p>{t('home.reportClearlyBody')}</p>
        </div>
        <div>
          <span>02</span>
          <h2>{t('home.followProgress')}</h2>
          <p>{t('home.followProgressBody')}</p>
        </div>
        <div>
          <span>03</span>
          <h2>{t('home.exploreSafely')}</h2>
          <p>{t('home.exploreSafelyBody')}</p>
        </div>
      </section>
      <section className="landing-community">
        <div>
          <span className="eyebrow">{t('home.happening')}</span>
          <h2>{t('home.clearerView')}</h2>
          <p className="lede">{t('home.publicProjection')}</p>
        </div>
        <div className="button-row">
          <Link className="button" to="/reports">
            {t('home.browsePublic')}
          </Link>
          <Link className="button button-secondary" to="/map">
            {t('home.openMap')}
          </Link>
        </div>
      </section>
    </div>
  );
}

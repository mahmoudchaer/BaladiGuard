import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useCitizenAuth } from '@/auth/CitizenAuthContext';
import { getHistory } from '@/services/contributions';
import type { CitizenTicketHistoryItem } from '@/types/ticket';

function formatCategory(category: string | null): string {
  if (!category) {
    return 'General';
  }
  return category.replaceAll('_', ' ');
}

export function HomePage() {
  const auth = useCitizenAuth();
  if (auth.isAuthenticated) return <CitizenHome />;
  return <PublicHome />;
}

function CitizenHome() {
  const { profile } = useCitizenAuth();
  const [reports, setReports] = useState<CitizenTicketHistoryItem[]>([]);
  const [error, setError] = useState(false);
  useEffect(() => {
    void getHistory(3)
      .then((page) => setReports(page.items))
      .catch(() => setError(true));
  }, []);
  const firstName = profile?.fullName?.trim().split(/\s+/)[0];
  const active = reports.filter((item) => !['RESOLVED', 'CLOSED'].includes(item.status)).length;
  return (
    <section className="citizen-home page-enter">
      <div className="home-welcome">
        <div>
          <span className="eyebrow">
            {new Date().getHours() < 12
              ? 'GOOD MORNING'
              : new Date().getHours() < 18
                ? 'GOOD AFTERNOON'
                : 'GOOD EVENING'}
          </span>
          <h1>{firstName ? `Hello, ${firstName}` : 'Hello'}</h1>
          <p className="lede">See what needs attention and follow the city’s response.</p>
        </div>
      </div>
      <Link className="primary-action tactile" to="/report">
        <span className="action-icon">＋</span>
        <span>
          <strong>Report an issue</strong>
          <small>Photo, location, and a few details</small>
        </span>
        <span aria-hidden>→</span>
      </Link>
      <div className="quick-grid">
        <Link className="quick-card tactile" to="/track">
          <span>▦</span>
          <strong>Track a code</strong>
          <small>Open a private report</small>
        </Link>
        <Link className="quick-card tactile" to="/map">
          <span>⌖</span>
          <strong>Nearby</strong>
          <small>Browse public reports</small>
        </Link>
      </div>
      <div className="section-heading">
        <div>
          <h2>Your reports</h2>
          <span>{reports.length ? `${active} active` : 'Your activity'}</span>
        </div>
        <Link to="/history">View all</Link>
      </div>
      {error ? (
        <div className="notice notice-info">Couldn’t refresh. Your reports are safe.</div>
      ) : null}
      {!error && reports.length === 0 ? (
        <div className="empty-state compact">
          <span>✓</span>
          <h2>Nothing to follow yet</h2>
          <p>When you report an issue, its progress will appear here.</p>
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
              <span className="history-glyph">⌖</span>
              <div className="history-copy">
                <strong>{formatCategory(report.category)}</strong>
                <span>{report.locationAddress}</span>
              </div>
              <span className={`status status-${report.status.toLowerCase().replace('_', '-')}`}>
                {report.status.replaceAll('_', ' ')}
              </span>
              <span>›</span>
            </Link>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function PublicHome() {
  return (
    <div className="landing-page page-enter">
      <div className="public-hero">
        <div>
          <span className="eyebrow">WELCOME TO BALADIGUARD</span>
          <h1>
            Your city,
            <br />
            within reach.
          </h1>
          <p className="lede">
            Report what needs attention and follow the municipality’s response from one place.
          </p>
          <div className="button-row">
            <Link className="button button-large" to="/report">
              Report an issue →
            </Link>
            <Link className="button button-secondary button-large" to="/reports">
              Continue as guest
            </Link>
          </div>
          <p className="helper">A verified phone number is only needed when you submit.</p>
        </div>
        <div className="hero-symbol" aria-hidden>
          <div>⌖</div>
          <span>
            <i /> Built for your community
          </span>
        </div>
      </div>
      <section className="landing-features" aria-label="How BaladiGuard works">
        <div>
          <span>01</span>
          <h2>Report clearly</h2>
          <p>Add a photo, confirm the location, and explain what needs attention.</p>
        </div>
        <div>
          <span>02</span>
          <h2>Follow progress</h2>
          <p>See municipal updates through your private account or tracking code.</p>
        </div>
        <div>
          <span>03</span>
          <h2>Explore safely</h2>
          <p>Browse approved public reports without exposing citizen information.</p>
        </div>
      </section>
      <section className="landing-community">
        <div>
          <span className="eyebrow">SEE WHAT’S HAPPENING</span>
          <h2>A clearer view of your community.</h2>
          <p className="lede">
            Public reports are separated from your private account and shown through a privacy-safe
            projection.
          </p>
        </div>
        <div className="button-row">
          <Link className="button" to="/reports">
            Browse public reports →
          </Link>
          <Link className="button button-secondary" to="/map">
            Open the map
          </Link>
        </div>
      </section>
    </div>
  );
}

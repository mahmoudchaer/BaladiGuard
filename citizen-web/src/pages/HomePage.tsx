import { Link } from 'react-router-dom';
import { PublicPhoto } from '@/components/PublicPhoto';
import { usePublicReportsFeed } from '@/hooks/usePublicReportsFeed';
import type { PublicTicketResponse } from '@/types/ticket';

function formatCategory(category: string | null): string {
  if (!category) {
    return 'General';
  }
  return category.replaceAll('_', ' ');
}

function ReportCard({ report }: { report: PublicTicketResponse }) {
  return (
    <Link className="report-card" to={`/public/${report.ticketNumber}`}>
      <span className="badge">{report.status.replaceAll('_', ' ')}</span>
      <strong>{report.ticketNumber}</strong>
      <span className="muted">{formatCategory(report.category)}</span>
      <p style={{ margin: 0 }}>{report.description}</p>
      <span className="muted">{report.location.addressText}</span>
    </Link>
  );
}

export function HomePage() {
  const { items, nextCursor, loading, loadingMore, error, reload, loadMore } =
    usePublicReportsFeed();

  return (
    <div className="page">
      <h1>Public reports</h1>
      <p className="lede">
        Browse published community reports without an account. Prefer a map? Open the map view — a
        list remains available here for accessibility.
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
        <Link className="button" to="/map">
          Open map
        </Link>
        <Link className="button button-secondary" to="/track">
          Track by code
        </Link>
      </div>

      {error ? (
        <div className="error-banner" role="alert">
          <p style={{ margin: '0 0 0.75rem' }}>{error}</p>
          <button type="button" className="button" onClick={() => void reload()}>
            Try again
          </button>
        </div>
      ) : null}

      {loading ? <p className="muted">Loading public reports…</p> : null}

      {!loading && !error && items.length === 0 ? (
        <div className="panel">
          <p style={{ margin: 0 }}>No public reports are available right now.</p>
        </div>
      ) : null}

      {!loading && items.length > 0 ? (
        <div className="stack" data-testid="public-report-list">
          {items.map((report) => (
            <article key={report.ticketNumber} className="panel" style={{ padding: 0 }}>
              <div style={{ display: 'grid', gap: '0.75rem', padding: '1rem' }}>
                <PublicPhoto
                  photoUrl={report.photoUrl}
                  alt={`Public photo for ${report.ticketNumber}`}
                />
                <ReportCard report={report} />
              </div>
            </article>
          ))}
          {nextCursor ? (
            <button
              type="button"
              className="button"
              disabled={loadingMore}
              onClick={() => void loadMore()}
            >
              {loadingMore ? 'Loading…' : 'Load more'}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

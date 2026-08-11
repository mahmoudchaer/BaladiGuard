import { Link } from 'react-router-dom';
import { PublicReportsMap } from '@/components/PublicReportsMap';
import { usePublicReportsFeed } from '@/hooks/usePublicReportsFeed';

export function MapPage() {
  const { items, loading, error, reload } = usePublicReportsFeed();

  return (
    <div className="page">
      <h1>Public map</h1>
      <p className="lede">
        Published reports with map locations appear below. Nearby pins cluster at wider zoom. Prefer
        a list? Use the accessible list view.
      </p>
      <Link className="button button-secondary" to="/">
        View as list
      </Link>

      {error ? (
        <div className="error-banner" role="alert">
          <p style={{ margin: '0 0 0.75rem' }}>{error}</p>
          <button type="button" className="button" onClick={() => void reload()}>
            Try again
          </button>
        </div>
      ) : null}

      {loading ? <p className="muted">Loading map…</p> : null}

      {!loading && !error ? <PublicReportsMap reports={items} /> : null}
    </div>
  );
}

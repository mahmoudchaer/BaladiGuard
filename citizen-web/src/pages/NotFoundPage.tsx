import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <div className="page" data-testid="not-found-page">
      <h1>Page not found</h1>
      <div className="panel stack">
        <p style={{ margin: 0, lineHeight: 1.55 }}>
          That address is not a BaladiGuard citizen page. Check the link, or return to public
          reports.
        </p>
        <Link className="button" to="/">
          Browse public reports
        </Link>
        <Link to="/track">Track a report by code</Link>
      </div>
    </div>
  );
}

import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { PublicPhoto } from '@/components/PublicPhoto';
import { PUBLIC_TICKETS_NETWORK_MESSAGE, getPublicTickets } from '@/services/tickets';
import type { PublicTicketResponse } from '@/types/ticket';
import { t } from '@/i18n';

const PAGE_SIZE = 6;
const CATEGORIES = [
  'road_damage',
  'waste',
  'street_lighting',
  'water_leak',
  'noise',
  'sidewalk_damage',
  'traffic_signal',
  'drainage',
  'public_facilities',
];
const STATUSES = ['SUBMITTED', 'UNDER_REVIEW', 'ASSIGNED', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'];

function formatCategory(category: string | null): string {
  return (category ?? 'General').replaceAll('_', ' ');
}

export function PublicReportsPage() {
  const [pages, setPages] = useState<Record<number, PublicTicketResponse[]>>({});
  const [cursors, setCursors] = useState<Array<string | null>>([null]);
  const [nextCursors, setNextCursors] = useState<Record<number, string | null>>({});
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [category, setCategory] = useState('');
  const requestRef = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);

  const loadPage = useCallback(
    async (target: number) => {
      if (pages[target]) {
        setPage(target);
        return;
      }
      const cursor = cursors[target];
      if (cursor === undefined) return;
      const request = ++requestRef.current;
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;
      setLoading(true);
      setError(null);
      try {
        const result = await getPublicTickets({
          limit: PAGE_SIZE,
          cursor,
          q: query,
          status,
          category,
          signal: controller.signal,
        });
        if (request !== requestRef.current) return;
        setPages((current) => ({ ...current, [target]: result.items }));
        setNextCursors((current) => ({ ...current, [target]: result.nextCursor }));
        if (result.nextCursor) {
          setCursors((current) => {
            const next = [...current];
            next[target + 1] = result.nextCursor;
            return next;
          });
        }
        setPage(target);
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : PUBLIC_TICKETS_NETWORK_MESSAGE);
      } finally {
        if (request === requestRef.current) setLoading(false);
      }
    },
    [category, cursors, pages, query, status],
  );

  useEffect(() => {
    const timer = setTimeout(() => setQuery(searchInput.trim()), 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    controllerRef.current?.abort();
    requestRef.current += 1;
    setPages({});
    setCursors([null]);
    setNextCursors({});
    setPage(0);
    setError(null);
    setLoading(true);
  }, [query, status, category]);

  useEffect(() => () => controllerRef.current?.abort(), []);

  useEffect(() => {
    if (!pages[0]) void loadPage(0);
  }, [loadPage, pages]);

  const items = pages[page] ?? [];
  const canGoNext = Boolean(nextCursors[page]);
  const highestLoadedPage = Math.max(page, ...Object.keys(pages).map(Number));
  const visiblePages = Array.from(
    { length: highestLoadedPage + (nextCursors[highestLoadedPage] ? 2 : 1) },
    (_, index) => index,
  );

  return (
    <section className="page page-enter reports-directory">
      <div className="directory-heading">
        <div>
          <span className="eyebrow">COMMUNITY ACTIVITY</span>
          <h1>{t('public.title')}</h1>
          <p className="lede">Browse approved, privacy-safe reports shared across the community.</p>
        </div>
        <div className="button-row">
          <Link className="button button-secondary" to="/map">
            Map view
          </Link>
          <Link className="button" to="/report">
            Report an issue
          </Link>
        </div>
      </div>

      <div className="report-filters" role="search" aria-label="Search and filter reports">
        <label className="report-search">
          <span className="sr-only">Search public reports</span>
          <span aria-hidden="true">⌕</span>
          <input
            type="search"
            aria-label="Search public reports"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Search report number, issue, or area"
          />
        </label>
        <label>
          <span className="sr-only">Filter by status</span>
          <select
            aria-label="Filter by status"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">All statuses</option>
            {STATUSES.map((value) => (
              <option key={value} value={value}>
                {value.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="sr-only">Filter by category</span>
          <select
            aria-label="Filter by category"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            <option value="">All categories</option>
            {CATEGORIES.map((value) => (
              <option key={value} value={value}>
                {formatCategory(value)}
              </option>
            ))}
          </select>
        </label>
        {searchInput || status || category ? (
          <button
            type="button"
            className="text-button clear-filters"
            onClick={() => {
              setSearchInput('');
              setQuery('');
              setStatus('');
              setCategory('');
            }}
          >
            Clear
          </button>
        ) : null}
      </div>

      {error ? (
        <div className="notice notice-error" role="alert">
          {error}
          <button className="text-button" onClick={() => void loadPage(page)}>
            Retry
          </button>
        </div>
      ) : null}
      {loading ? (
        <div className="loading-state" role="status">
          Loading page {page + 1}…
        </div>
      ) : null}
      {!loading && !error && items.length === 0 ? (
        <div className="empty-state">
          <span>✓</span>
          <h2>{query || status || category ? 'No matching reports' : 'No public reports yet'}</h2>
          <p>
            {query || status || category
              ? 'Try changing or clearing your search filters.'
              : 'Approved community reports will appear here.'}
          </p>
        </div>
      ) : null}

      {!loading && items.length > 0 ? (
        <div className="public-report-grid" data-testid="public-report-list">
          {items.map((report) => (
            <article className="public-report-tile" key={report.ticketNumber}>
              <PublicPhoto
                photoUrl={report.photoUrl}
                alt={`Public photo for ${report.ticketNumber}`}
              />
              <Link className="report-card" to={`/public/${report.ticketNumber}`}>
                <div className="tile-meta">
                  <span className="badge">{report.status.replaceAll('_', ' ')}</span>
                  <strong>{report.ticketNumber}</strong>
                </div>
                <span className="muted">{formatCategory(report.category)}</span>
                <p>{report.description}</p>
                <span className="muted tile-location">⌖ {report.location.addressText}</span>
              </Link>
            </article>
          ))}
        </div>
      ) : null}

      {!loading && (items.length > 0 || page > 0) ? (
        <nav className="pagination" aria-label="Report pages">
          <button
            className="page-control"
            disabled={page === 0}
            onClick={() => void loadPage(page - 1)}
          >
            ← Previous
          </button>
          <div className="page-numbers">
            {visiblePages.map((index) => (
              <button
                className={index === page ? 'page-number page-number-active' : 'page-number'}
                aria-current={index === page ? 'page' : undefined}
                key={index}
                onClick={() => void loadPage(index)}
              >
                {index + 1}
              </button>
            ))}
          </div>
          <button
            className="page-control"
            disabled={!canGoNext}
            onClick={() => void loadPage(page + 1)}
          >
            {t('public.next')}
          </button>
        </nav>
      ) : null}
    </section>
  );
}

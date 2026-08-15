import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getHistory, submitResolutionFeedback } from '@/services/contributions';
import type { CitizenTicketHistoryItem, ResolutionFeedbackStatus } from '@/types/ticket';

function label(value: string | null): string {
  if (!value) return 'General report';
  return value.replaceAll('_', ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

export function HistoryPage() {
  const [items, setItems] = useState<CitizenTicketHistoryItem[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [submittingCode, setSubmittingCode] = useState<string | null>(null);

  const load = useCallback(async (next?: string | null) => {
    setLoading(true);
    setError(null);
    try {
      const page = await getHistory(20, next);
      setItems((current) => (next ? [...current, ...page.items] : page.items));
      setCursor(page.nextCursor);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load your reports.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleFeedback = async (trackingCode: string, status: ResolutionFeedbackStatus) => {
    setSubmittingCode(trackingCode);
    setFeedbackError(null);
    try {
      const result = await submitResolutionFeedback(trackingCode, status);
      setItems((current) =>
        current.map((item) =>
          item.trackingCode === trackingCode
            ? {
                ...item,
                canSubmitResolutionFeedback: result.canSubmit,
                resolutionFeedbackStatus: result.status,
              }
            : item,
        ),
      );
    } catch (err) {
      setFeedbackError(err instanceof Error ? err.message : 'Unable to submit feedback.');
    } finally {
      setSubmittingCode(null);
    }
  };

  return (
    <section className="page page-enter narrow-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">YOUR ACTIVITY</span>
          <h1>My reports</h1>
          <p className="lede">Follow every issue you have shared with the municipality.</p>
        </div>
        <Link className="button" to="/report">
          ＋ New report
        </Link>
      </div>
      {error ? (
        <div className="notice notice-error" role="alert">
          {error}
          <button className="text-button" onClick={() => void load()}>
            Retry
          </button>
        </div>
      ) : null}
      {!loading && !error && items.length === 0 ? (
        <div className="empty-state">
          <span>✓</span>
          <h2>Nothing to follow yet</h2>
          <p>When you submit a report, its progress will appear here.</p>
          <Link className="button" to="/report">
            Report an issue
          </Link>
        </div>
      ) : null}
      {items.length ? (
        <div className="history-list">
          {items.map((item) => (
            <article className="history-row" key={item.trackingCode}>
              <Link className="history-row tactile" to={`/track?trackingCode=${item.trackingCode}`}>
                <span className="history-glyph">⌖</span>
                <div className="history-copy">
                  <strong>{label(item.category)}</strong>
                  <span>{item.locationAddress}</span>
                  <small>{new Date(item.submittedAt).toLocaleDateString()}</small>
                </div>
                <span className={`status status-${item.status.toLowerCase().replace('_', '-')}`}>
                  {item.status.replaceAll('_', ' ')}
                </span>
                <span aria-hidden>›</span>
              </Link>
              {item.canSubmitResolutionFeedback || item.resolutionFeedbackStatus ? (
                <div className="history-feedback">
                  <p>
                    {item.resolutionFeedbackStatus === 'CONFIRMED_FIXED'
                      ? 'You confirmed this report was fixed.'
                      : item.resolutionFeedbackStatus === 'STILL_UNRESOLVED'
                        ? 'You told the municipality this is still unresolved.'
                        : 'Was this issue fixed?'}
                  </p>
                  <button
                    type="button"
                    className="button button-secondary"
                    disabled={submittingCode === item.trackingCode}
                    onClick={() => void handleFeedback(item.trackingCode, 'CONFIRMED_FIXED')}
                  >
                    Confirmed fixed
                  </button>
                  <button
                    type="button"
                    className="button button-secondary"
                    disabled={submittingCode === item.trackingCode}
                    onClick={() => void handleFeedback(item.trackingCode, 'STILL_UNRESOLVED')}
                  >
                    Still unresolved
                  </button>
                </div>
              ) : null}
            </article>
          ))}
          {feedbackError ? (
            <div className="notice notice-error" role="alert">
              {feedbackError}
            </div>
          ) : null}
        </div>
      ) : null}
      {loading ? (
        <div className="loading-state" role="status">
          Loading your reports…
        </div>
      ) : null}
      {cursor && !loading ? (
        <button className="button button-secondary load-more" onClick={() => void load(cursor)}>
          Load more
        </button>
      ) : null}
    </section>
  );
}

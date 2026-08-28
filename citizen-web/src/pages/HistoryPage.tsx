import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getHistory, submitResolutionFeedback } from '@/services/contributions';
import type { CitizenTicketHistoryItem, ResolutionFeedbackStatus } from '@/types/ticket';
import { StatusChip } from '@/components/StatusChip';
import { translateCategory } from '@/i18n';
import { useI18n } from '@/i18n/LocaleProvider';

function label(value: string | null, fallback: string): string {
  if (!value) return fallback;
  return translateCategory(value);
}

export function HistoryPage() {
  const { t, locale } = useI18n();
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
      setError(err instanceof Error ? err.message : t('history.loadFailed'));
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
      setFeedbackError(err instanceof Error ? err.message : t('history.feedbackFailed'));
    } finally {
      setSubmittingCode(null);
    }
  };

  return (
    <section className="page page-enter narrow-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('history.eyebrow')}</span>
          <h1>{t('history.title')}</h1>
          <p className="lede">{t('history.lede')}</p>
        </div>
        <Link className="button" to="/report">
          {t('history.newReport')}
        </Link>
      </div>
      {error ? (
        <div className="notice notice-error" role="alert">
          {error}
          <button className="text-button" onClick={() => void load()}>
            {t('common.retry')}
          </button>
        </div>
      ) : null}
      {!loading && !error && items.length === 0 ? (
        <div className="empty-state">
          <span>✓</span>
          <h2>{t('history.emptyTitle')}</h2>
          <p>{t('history.emptyBody')}</p>
          <Link className="button" to="/report">
            {t('history.reportIssue')}
          </Link>
        </div>
      ) : null}
      {items.length ? (
        <div className="history-list">
          {items.map((item) => (
            <article className="history-row" key={item.trackingCode}>
              <Link className="history-row tactile" to={`/track?trackingCode=${item.trackingCode}`}>
                <span className="history-glyph" aria-hidden>
                  ⌖
                </span>
                <div className="history-copy">
                  <strong>{label(item.category, t('history.generalReport'))}</strong>
                  <span>{item.locationAddress}</span>
                  <small>{new Date(item.submittedAt).toLocaleDateString(locale)}</small>
                </div>
                <StatusChip status={item.status} />
                <span aria-hidden>›</span>
              </Link>
              {item.canSubmitResolutionFeedback || item.resolutionFeedbackStatus ? (
                <div className="history-feedback">
                  <p>
                    {item.resolutionFeedbackStatus === 'CONFIRMED_FIXED'
                      ? t('history.confirmed')
                      : item.resolutionFeedbackStatus === 'STILL_UNRESOLVED'
                        ? t('history.unresolved')
                        : t('history.askFixed')}
                  </p>
                  <button
                    type="button"
                    className="button button-secondary"
                    disabled={submittingCode === item.trackingCode}
                    onClick={() => void handleFeedback(item.trackingCode, 'CONFIRMED_FIXED')}
                  >
                    {t('history.confirmedFixed')}
                  </button>
                  <button
                    type="button"
                    className="button button-secondary"
                    disabled={submittingCode === item.trackingCode}
                    onClick={() => void handleFeedback(item.trackingCode, 'STILL_UNRESOLVED')}
                  >
                    {t('history.stillUnresolved')}
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
          {t('history.loading')}
        </div>
      ) : null}
      {cursor && !loading ? (
        <button className="button button-secondary load-more" onClick={() => void load(cursor)}>
          {t('history.loadMore')}
        </button>
      ) : null}
    </section>
  );
}

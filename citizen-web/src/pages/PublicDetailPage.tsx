import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { PublicPhoto } from '@/components/PublicPhoto';
import { translateCategory, translateStatus } from '@/i18n';
import { useI18n } from '@/i18n/LocaleProvider';
import {
  PUBLIC_TICKET_NETWORK_MESSAGE,
  PUBLIC_TICKET_NOT_FOUND_MESSAGE,
  getPublicTicketByNumber,
} from '@/services/tickets';
import type { PublicTicketResponse } from '@/types/ticket';

export function PublicDetailPage() {
  const { t } = useI18n();
  const { ticketNumber = '' } = useParams();
  const [report, setReport] = useState<PublicTicketResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void getPublicTicketByNumber(ticketNumber)
      .then((item) => {
        if (!cancelled) {
          setReport(item);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setReport(null);
          setError(
            err instanceof Error
              ? err.message === PUBLIC_TICKET_NOT_FOUND_MESSAGE
                ? t('public.detailNotFound')
                : err.message === PUBLIC_TICKET_NETWORK_MESSAGE
                  ? t('public.detailNetwork')
                  : err.message
              : t('public.detailNetwork'),
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [ticketNumber]);

  return (
    <div className="page">
      <Link to="/">{t('public.back')}</Link>
      <h1>{t('public.detailTitle')}</h1>

      {loading ? <p className="muted">{t('public.loadingDetail')}</p> : null}

      {error ? (
        <div className="error-banner" role="alert">
          {error}
        </div>
      ) : null}

      {report ? (
        <article className="panel stack" data-testid="public-detail">
          <PublicPhoto
            photoUrl={report.photoUrl}
            alt={t('public.photoAlt', { ticketNumber: report.ticketNumber })}
          />
          <span className="badge">{translateStatus(report.status)}</span>
          <h2 style={{ margin: 0 }}>{report.ticketNumber}</h2>
          <p className="muted" style={{ margin: 0 }}>
            {translateCategory(report.category)} · {report.attribution.displayName}
          </p>
          <p style={{ margin: 0, lineHeight: 1.5 }}>{report.description}</p>
          <p className="muted" style={{ margin: 0 }}>
            {report.location.addressText}
          </p>
          {report.department?.name ? (
            <p className="muted" style={{ margin: 0 }}>
              {t('common.department', { name: report.department.name })}
            </p>
          ) : null}
        </article>
      ) : null}
    </div>
  );
}

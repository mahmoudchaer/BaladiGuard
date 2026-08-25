import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { PublicPhoto } from '@/components/PublicPhoto';
import { StatusChip } from '@/components/StatusChip';
import { translateCategory } from '@/i18n';
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
  const requestGeneration = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(() => {
    const generation = requestGeneration.current + 1;
    requestGeneration.current = generation;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    setReport(null);
    void getPublicTicketByNumber(ticketNumber, { signal: controller.signal })
      .then((item) => {
        if (generation === requestGeneration.current) setReport(item);
      })
      .catch((err: unknown) => {
        if (generation !== requestGeneration.current) return;
        if (err instanceof Error && err.name === 'AbortError') return;
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
      })
      .finally(() => {
        if (generation === requestGeneration.current) setLoading(false);
      });
    return () => {
      controller.abort();
    };
  }, [ticketNumber, t]);

  useEffect(() => load(), [load]);

  return (
    <div className="page">
      <Link to="/reports">{t('public.back')}</Link>
      <h1>{t('public.detailTitle')}</h1>

      {loading ? <p className="muted">{t('public.loadingDetail')}</p> : null}

      {error ? (
        <div className="error-banner" role="alert">
          <p style={{ margin: '0 0 0.75rem' }}>{error}</p>
          <button type="button" className="button" onClick={() => load()}>
            {t('common.tryAgain')}
          </button>
        </div>
      ) : null}

      {report ? (
        <article className="panel stack" data-testid="public-detail">
          <PublicPhoto
            photoUrl={report.photoUrl}
            alt={t('public.photoAlt', { ticketNumber: report.ticketNumber })}
          />
          <StatusChip status={report.status} />
          <h2 className="ltr-isolate" style={{ margin: 0 }}>
            {report.ticketNumber}
          </h2>
          <p className="muted" style={{ margin: 0 }}>
            {translateCategory(report.category)} · {report.attribution.displayName}
          </p>
          <p style={{ margin: 0, lineHeight: 1.5 }}>{report.description}</p>
          <p className="muted" style={{ margin: 0 }}>
            {report.location.addressText}
          </p>
          {Number.isFinite(report.mapLocation.latitude) &&
          Number.isFinite(report.mapLocation.longitude) ? (
            <a
              className="button button-secondary"
              href={`https://www.google.com/maps?q=${report.mapLocation.latitude},${report.mapLocation.longitude}`}
              target="_blank"
              rel="noreferrer"
            >
              {t('public.openInMaps')}
            </a>
          ) : null}
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

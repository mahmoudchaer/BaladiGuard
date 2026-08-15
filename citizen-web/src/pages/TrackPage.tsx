import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  TRACK_LOOKUP_INVALID_MESSAGE,
  TRACK_LOOKUP_NETWORK_MESSAGE,
  TRACK_LOOKUP_NOT_FOUND_MESSAGE,
  getTicketByTrackingCode,
} from '@/services/tickets';
import type { CitizenTicketResponse } from '@/types/ticket';
import { isValidTrackingCode, normalizeTrackingCode } from '@/utils/trackingCode';
import { translateCategory, translateStatus } from '@/i18n';
import { useI18n } from '@/i18n/LocaleProvider';

function localizeTrackError(message: string, translate: (key: string) => string): string {
  if (message === TRACK_LOOKUP_INVALID_MESSAGE) return translate('track.invalid');
  if (message === TRACK_LOOKUP_NOT_FOUND_MESSAGE) return translate('track.notFound');
  if (message === TRACK_LOOKUP_NETWORK_MESSAGE) return translate('track.network');
  return message;
}

export function TrackPage() {
  const { t, locale } = useI18n();
  const [params] = useSearchParams();
  const initial = normalizeTrackingCode(params.get('trackingCode') ?? params.get('code') ?? '');
  const [code, setCode] = useState(initial);
  const [result, setResult] = useState<CitizenTicketResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const didAutoLookup = useRef(false);

  async function lookup(value: string) {
    const normalized = normalizeTrackingCode(value);
    if (!isValidTrackingCode(normalized)) {
      setResult(null);
      setError(t('track.invalid'));
      return;
    }
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const ticket = await getTicketByTrackingCode(normalized);
      setResult(ticket);
    } catch (err) {
      setError(err instanceof Error ? localizeTrackError(err.message, t) : t('errors.generic'));
    } finally {
      setSubmitting(false);
    }
  }

  useEffect(() => {
    if (!initial || didAutoLookup.current) {
      return;
    }
    didAutoLookup.current = true;
    void lookup(initial);
  }, [initial]);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void lookup(code);
  }

  return (
    <div className="page">
      <h1>{t('track.title')}</h1>
      <p className="lede">{t('track.subtitle')}</p>

      <form className="panel stack" onSubmit={onSubmit}>
        <label htmlFor="tracking-code">
          {t('track.codeLabel')}
          <input
            id="tracking-code"
            className="input"
            name="trackingCode"
            value={code}
            onChange={(event) => setCode(normalizeTrackingCode(event.target.value))}
            maxLength={6}
            autoComplete="off"
            spellCheck={false}
            aria-describedby="tracking-help"
          />
        </label>
        <p id="tracking-help" className="muted" style={{ margin: 0 }}>
          {t('track.hint')}
        </p>
        <button type="submit" className="button" disabled={submitting}>
          {submitting ? t('common.lookingUp') : t('common.lookUp')}
        </button>
      </form>

      {error ? (
        <div className="error-banner" role="alert">
          {error}
        </div>
      ) : null}

      {result ? (
        <article className="panel stack" data-testid="track-result">
          <span className="badge">{translateStatus(result.status)}</span>
          <h2 className="ltr-isolate" style={{ margin: 0 }}>
            {result.ticketNumber ?? t('track.reportFallback')}
          </h2>
          <p className="muted ltr-isolate" style={{ margin: 0 }}>
            {t('track.codeValue', { code: result.trackingCode })}
          </p>
          <p style={{ margin: 0 }}>
            {translateCategory(result.category)}
            {result.location?.addressText ? ` · ${result.location.addressText}` : ''}
          </p>
          {result.department?.name ? (
            <p className="muted" style={{ margin: 0 }}>
              {t('common.department', { name: result.department.name })}
            </p>
          ) : null}
          <div>
            <h3 style={{ margin: '0 0 0.5rem' }}>{t('track.timeline')}</h3>
            <ol style={{ margin: 0, paddingLeft: '1.2rem' }}>
              {result.timeline.map((entry) => (
                <li key={`${entry.status}-${entry.changedAt}`}>
                  {translateStatus(entry.status)} —{' '}
                  {new Date(entry.changedAt).toLocaleString(locale)}
                </li>
              ))}
            </ol>
          </div>
        </article>
      ) : null}
    </div>
  );
}

import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { CopyButton } from '@/components/CopyButton';
import { StatusChip } from '@/components/StatusChip';
import {
  TRACK_LOOKUP_INVALID_MESSAGE,
  TRACK_LOOKUP_NETWORK_MESSAGE,
  TRACK_LOOKUP_NOT_FOUND_MESSAGE,
  getTicketByTrackingCode,
} from '@/services/tickets';
import type { CitizenTicketResponse } from '@/types/ticket';
import { isValidTrackingCode, normalizeTrackingCode } from '@/utils/trackingCode';
import {
  describeNextAction,
  describeStatusMeaning,
  translateCategory,
  translateStatus,
} from '@/i18n';
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
  const [lookedUp, setLookedUp] = useState(Boolean(initial));
  const didAutoLookup = useRef(false);

  async function lookup(value: string) {
    const normalized = normalizeTrackingCode(value);
    setLookedUp(true);
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

      {!lookedUp && !result && !error ? (
        <div className="empty-state compact">
          <span>▦</span>
          <h2>{t('track.emptyTitle')}</h2>
          <p>{t('track.emptyBody')}</p>
        </div>
      ) : null}

      {error ? (
        <div className="error-banner" role="alert">
          {error}
        </div>
      ) : null}

      {result ? (
        <article className="panel stack" data-testid="track-result">
          <StatusChip status={result.status} />
          <h2 className="ltr-isolate" style={{ margin: 0 }}>
            {result.ticketNumber ?? t('track.reportFallback')}
          </h2>
          <div className="track-code-row">
            <p className="muted ltr-isolate" style={{ margin: 0 }}>
              {t('track.codeValue', { code: result.trackingCode })}
            </p>
            <CopyButton value={result.trackingCode} label={t('track.copyCode')} />
          </div>
          <p style={{ margin: 0 }}>
            {translateCategory(result.category)}
            {result.location?.addressText ? ` · ${result.location.addressText}` : ''}
          </p>
          {result.department?.name ? (
            <p className="muted" style={{ margin: 0 }}>
              {t('common.department', { name: result.department.name })}
            </p>
          ) : null}
          <div className="track-guidance">
            <strong>{t('track.whatItMeans')}</strong>
            <p style={{ margin: 0 }}>{describeStatusMeaning(result.status)}</p>
            <strong>{t('track.whatHappensNext')}</strong>
            <p style={{ margin: 0 }}>{describeNextAction(result.status)}</p>
          </div>
          {result.outcomeMessage ? (
            <p data-testid="track-outcome" style={{ margin: 0 }}>
              {result.outcomeMessage}
            </p>
          ) : null}
          <div>
            <h3 style={{ margin: '0 0 0.5rem' }}>{t('track.timeline')}</h3>
            <ol style={{ margin: 0, paddingInlineStart: '1.2rem' }}>
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

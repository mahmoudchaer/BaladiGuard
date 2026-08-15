import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { TRACK_LOOKUP_INVALID_MESSAGE, getTicketByTrackingCode } from '@/services/tickets';
import type { CitizenTicketResponse } from '@/types/ticket';
import { isValidTrackingCode, normalizeTrackingCode } from '@/utils/trackingCode';

export function TrackPage() {
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
      setError(TRACK_LOOKUP_INVALID_MESSAGE);
      return;
    }
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const ticket = await getTicketByTrackingCode(normalized);
      setResult(ticket);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
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
      <h1>Track a report</h1>
      <p className="lede">
        Enter the 6-character tracking code from your submission confirmation. We look it up without
        requiring an account.
      </p>

      <form className="panel stack" onSubmit={onSubmit}>
        <label htmlFor="tracking-code">
          Tracking code
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
          Your tracking code was shown on the confirmation screen when you submitted a report.
        </p>
        <button type="submit" className="button" disabled={submitting}>
          {submitting ? 'Looking up…' : 'Look up'}
        </button>
      </form>

      {error ? (
        <div className="error-banner" role="alert">
          {error}
        </div>
      ) : null}

      {result ? (
        <article className="panel stack" data-testid="track-result">
          <span className="badge">{result.status.replaceAll('_', ' ')}</span>
          <h2 style={{ margin: 0 }}>{result.ticketNumber ?? 'Report'}</h2>
          <p className="muted" style={{ margin: 0 }}>
            Tracking code: {result.trackingCode}
          </p>
          <p style={{ margin: 0 }}>
            {result.category?.replaceAll('_', ' ') ?? 'General'}
            {result.location?.addressText ? ` · ${result.location.addressText}` : ''}
          </p>
          {result.department?.name ? (
            <p className="muted" style={{ margin: 0 }}>
              Department: {result.department.name}
            </p>
          ) : null}
          {result.outcomeMessage ? (
            <p data-testid="track-outcome" style={{ margin: 0 }}>
              {result.outcomeMessage}
            </p>
          ) : null}
          <div>
            <h3 style={{ margin: '0 0 0.5rem' }}>Timeline</h3>
            <ol style={{ margin: 0, paddingLeft: '1.2rem' }}>
              {result.timeline.map((entry) => (
                <li key={`${entry.status}-${entry.changedAt}`}>
                  {entry.status.replaceAll('_', ' ')} — {new Date(entry.changedAt).toLocaleString()}
                </li>
              ))}
            </ol>
          </div>
        </article>
      ) : null}
    </div>
  );
}

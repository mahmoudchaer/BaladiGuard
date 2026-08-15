import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { loginPath } from '@/auth/returnTo';
import { useCitizenAuth } from '@/auth/CitizenAuthContext';
import { ApiError } from '@/services/api';
import {
  createTicket,
  uploadPhoto,
  validateLocation,
  type ValidatedLocation,
} from '@/services/contributions';
import {
  GUEST_DRAFT_USER_ID,
  clearDraft,
  loadDraft,
  newSubmissionId,
  saveDraft,
} from '@/services/reportDraft';
import type { SubmitTicketResponse } from '@/types/ticket';
import { t } from '@/i18n';

type Phase = 'idle' | 'validating' | 'uploading' | 'submitting';

export function ReportPage() {
  const { profile, logout } = useCitizenAuth();
  const navigate = useNavigate();
  const authenticatedUserId = profile?.userId;
  const userId = authenticatedUserId ?? GUEST_DRAFT_USER_ID;
  const [description, setDescription] = useState('');
  const [addressText, setAddress] = useState('');
  const [location, setLocation] = useState<ValidatedLocation | null>(null);
  const [photo, setPhoto] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [submissionId, setSubmissionId] = useState(newSubmissionId);
  const [uploadedKey, setUploadedKey] = useState<string | undefined>();
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState<string | null>(null);
  const [restored, setRestored] = useState(false);
  const [result, setResult] = useState<SubmitTicketResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      let draft = await loadDraft(userId);
      if (!authenticatedUserId && draft && Date.now() - draft.updatedAt >= 24 * 60 * 60 * 1000) {
        await clearDraft(GUEST_DRAFT_USER_ID);
        draft = null;
      }
      if (!draft && authenticatedUserId) {
        const guestDraft = await loadDraft(GUEST_DRAFT_USER_ID);
        const isRecent = guestDraft && Date.now() - guestDraft.updatedAt < 24 * 60 * 60 * 1000;
        if (isRecent && guestDraft) {
          draft = { ...guestDraft, userId: authenticatedUserId };
          await saveDraft(draft);
          await clearDraft(GUEST_DRAFT_USER_ID);
        } else if (guestDraft) {
          await clearDraft(GUEST_DRAFT_USER_ID);
        }
      }
      if (!draft || cancelled) return;
      setDescription(draft.description);
      setAddress(draft.addressText);
      setLocation(draft.location);
      setSubmissionId(draft.clientSubmissionId);
      setUploadedKey(draft.imageObjectKey);
      setRestored(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [authenticatedUserId, userId]);

  useEffect(() => {
    if (!description && !addressText && !location && !uploadedKey) return;
    const timer = window.setTimeout(() => {
      void saveDraft({
        userId,
        description,
        addressText,
        location,
        clientSubmissionId: submissionId,
        imageObjectKey: uploadedKey,
        updatedAt: Date.now(),
      });
    }, 350);
    return () => window.clearTimeout(timer);
  }, [userId, description, addressText, location, submissionId, uploadedKey]);

  useEffect(
    () => () => {
      if (preview) URL.revokeObjectURL(preview);
    },
    [preview],
  );
  const busy = phase !== 'idle';
  const progress =
    phase === 'validating' ? 25 : phase === 'uploading' ? 55 : phase === 'submitting' ? 82 : 0;
  const photoLabel = useMemo(
    () =>
      photo
        ? `${photo.name} · ${(photo.size / 1024 / 1024).toFixed(1)} MB`
        : uploadedKey
          ? 'Previously uploaded photo ready'
          : '',
    [photo, uploadedKey],
  );

  async function getDeviceLocation() {
    setError(null);
    setPhase('validating');
    if (!navigator.geolocation) {
      setError('Location services are not available in this browser.');
      setPhase('idle');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) =>
        void validateLocation({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        })
          .then((next) => {
            setLocation(next);
            setAddress(next.addressText);
          })
          .catch((err: unknown) =>
            setError(err instanceof Error ? err.message : 'Unable to validate your location.'),
          )
          .finally(() => setPhase('idle')),
      () => {
        setError('We could not access your location. Enter an address instead.');
        setPhase('idle');
      },
      { enableHighAccuracy: true, timeout: 12000 },
    );
  }

  async function validateAddress() {
    if (addressText.trim().length < 3) {
      setError('Enter at least three characters for the location.');
      return;
    }
    setPhase('validating');
    setError(null);
    try {
      const next = await validateLocation({ addressText: addressText.trim() });
      setLocation(next);
      setAddress(next.addressText);
    } catch (err) {
      setLocation(null);
      setError(err instanceof Error ? err.message : 'Unable to validate that location.');
    } finally {
      setPhase('idle');
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (description.trim().length < 10) {
      setError('Describe the issue in at least 10 characters.');
      return;
    }
    if (description.trim().length > 2000) {
      setError('Description must be 2,000 characters or fewer.');
      return;
    }
    if (!location) {
      setError('Validate the report location before continuing.');
      return;
    }
    if (!profile) {
      await saveDraft({
        userId,
        description,
        addressText,
        location,
        clientSubmissionId: submissionId,
        updatedAt: Date.now(),
      });
      navigate(loginPath('/report'));
      return;
    }
    if (!photo && !uploadedKey) {
      setError('Choose a photo of the issue.');
      return;
    }
    try {
      let imageObjectKey = uploadedKey;
      if (!imageObjectKey) {
        setPhase('uploading');
        imageObjectKey = await uploadPhoto(photo!);
        setUploadedKey(imageObjectKey);
        await saveDraft({
          userId,
          description,
          addressText,
          location,
          clientSubmissionId: submissionId,
          imageObjectKey,
          updatedAt: Date.now(),
        });
      }
      setPhase('submitting');
      const next = await createTicket({
        description: description.trim(),
        location,
        imageObjectKey,
        clientSubmissionId: submissionId,
      });
      setResult(next);
      await clearDraft(userId);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) await logout();
      setError(
        `${err instanceof Error ? err.message : 'Unable to submit your report.'} Your draft is saved; retrying will not create a duplicate.`,
      );
    } finally {
      setPhase('idle');
    }
  }

  async function discard() {
    await clearDraft(userId);
    setDescription('');
    setAddress('');
    setLocation(null);
    setPhoto(null);
    setPreview(null);
    setUploadedKey(undefined);
    setSubmissionId(newSubmissionId());
    setRestored(false);
    setError(null);
  }

  if (result)
    return (
      <section className="success-page page-enter">
        <div className="success-mark">✓</div>
        <span className="eyebrow">REPORT RECEIVED</span>
        <h1>Thank you for speaking up.</h1>
        <p>The municipality can now review your report.</p>
        <div className="receipt-card">
          <span>Report</span>
          <strong>{result.ticketNumber}</strong>
          <span>Tracking code</span>
          <strong className="tracking-code">{result.trackingCode}</strong>
        </div>
        <div className="button-row">
          <Link className="button" to={`/track?trackingCode=${result.trackingCode}`}>
            View report
          </Link>
          <Link className="button button-secondary" to="/history">
            My reports
          </Link>
        </div>
      </section>
    );

  return (
    <section className="page page-enter report-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">NEW REPORT</span>
          <h1>{t('report.title')}</h1>
          <p className="lede">
            A clear photo, location, and short description help the municipality act faster.
          </p>
        </div>
        <span className="step-chip">
          {profile ? t('report.privateSubmission') : t('report.signInAtSubmit')}
        </span>
      </div>
      {restored ? (
        <div className="notice notice-info">
          Your saved draft was restored. Select the photo again if it was not already uploaded.
        </div>
      ) : null}
      {error ? (
        <div className="notice notice-error" role="alert">
          {error}
        </div>
      ) : null}
      {busy ? (
        <div className="submission-progress" role="status">
          <div style={{ width: `${progress}%` }} />
          <span>
            {phase === 'validating'
              ? 'Validating location…'
              : phase === 'uploading'
                ? 'Uploading photo…'
                : 'Submitting securely…'}
          </span>
        </div>
      ) : null}
      <form className="report-grid" onSubmit={(event) => void submit(event)}>
        <div className="report-main settings-card">
          <label className="field-label" htmlFor="description">
            Describe the issue
          </label>
          <textarea
            id="description"
            className="input textarea"
            maxLength={2000}
            placeholder="What happened? Include useful landmarks or safety concerns."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <span className="character-count">{description.length} / 2,000</span>
          <label className="field-label" htmlFor="address">
            Location
          </label>
          <div className="location-row">
            <input
              id="address"
              className="input"
              placeholder="Street, landmark, or neighborhood"
              value={addressText}
              onChange={(e) => {
                setAddress(e.target.value);
                setLocation(null);
              }}
            />
            <button
              className="button button-secondary"
              disabled={busy}
              type="button"
              onClick={() => void validateAddress()}
            >
              Check
            </button>
          </div>
          <button
            className="location-button"
            disabled={busy}
            type="button"
            onClick={() => void getDeviceLocation()}
          >
            <span aria-hidden>⌖</span>
            <span>
              <strong>Use my current location</strong>
              <small>Asked only when you choose this option</small>
            </span>
          </button>
          {location ? (
            <div className="validated-location">
              <span>✓</span>
              <div>
                <strong>Location confirmed</strong>
                <small>{location.addressText}</small>
              </div>
            </div>
          ) : null}
        </div>
        <aside className="report-side settings-card">
          <label className="field-label" htmlFor="photo">
            Photo
          </label>
          <label className="photo-drop" htmlFor="photo">
            {preview ? (
              <img src={preview} alt="Selected report preview" />
            ) : (
              <>
                <span className="photo-icon">＋</span>
                <strong>Choose a photo</strong>
                <small>JPEG, PNG, or WebP · up to 5 MB</small>
              </>
            )}
          </label>
          <input
            id="photo"
            className="visually-hidden"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={(e) => {
              const file = e.target.files?.[0] ?? null;
              if (file && file.size > 5 * 1024 * 1024) {
                setError('Photo must be 5 MB or smaller.');
                return;
              }
              setPhoto(file);
              setUploadedKey(undefined);
              if (preview) URL.revokeObjectURL(preview);
              setPreview(file ? URL.createObjectURL(file) : null);
            }}
          />
          {photoLabel ? <span className="helper">{photoLabel}</span> : null}
          <div className="privacy-callout">
            <span aria-hidden>◉</span>
            <p>
              <strong>Protected upload</strong>
              <br />
              Staff receive the private original. Public views only receive an approved redacted
              version.
            </p>
          </div>
          <button className="button button-large" disabled={busy} type="submit">
            {busy ? 'Please wait…' : 'Submit report'} <span aria-hidden>→</span>
          </button>
          <button
            className="text-button"
            disabled={busy}
            type="button"
            onClick={() => void discard()}
          >
            Discard draft
          </button>
        </aside>
      </form>
    </section>
  );
}

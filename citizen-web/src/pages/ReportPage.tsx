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
import { CopyButton } from '@/components/CopyButton';
import { CivicIllustration } from '@/components/CivicIllustration';
import { useI18n } from '@/i18n/LocaleProvider';

type Phase = 'idle' | 'validating' | 'uploading' | 'submitting';

export function ReportPage() {
  const { t } = useI18n();
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
  const [locating, setLocating] = useState(false);
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
          ? t('report.photoReady')
          : '',
    [photo, uploadedKey],
  );

  async function getDeviceLocation() {
    setError(null);
    setPhase('validating');
    setLocating(true);
    if (!navigator.geolocation) {
      setError(t('report.locationUnavailable'));
      setPhase('idle');
      setLocating(false);
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
            setError(err instanceof Error ? err.message : t('report.validateFailed')),
          )
          .finally(() => {
            setPhase('idle');
            setLocating(false);
          }),
      () => {
        setError(t('report.locationDenied'));
        setPhase('idle');
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 12000 },
    );
  }

  async function validateAddress() {
    if (addressText.trim().length < 3) {
      setError(t('report.locationTooShort'));
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
      setError(err instanceof Error ? err.message : t('report.addressFailed'));
    } finally {
      setPhase('idle');
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (description.trim().length < 10) {
      setError(t('report.descriptionShort'));
      return;
    }
    if (description.trim().length > 2000) {
      setError(t('report.descriptionLong'));
      return;
    }
    if (!location) {
      setError(t('report.needLocation'));
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
    if (!profile.contributionReady) {
      setError(t('report.notContributionReady'));
      return;
    }
    if (!photo && !uploadedKey) {
      setError(t('report.needPhoto'));
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
        `${err instanceof Error ? err.message : t('report.submitFailed')} ${t('report.draftSaved')}`,
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
        <CivicIllustration name="report-resolved" className="civic-illustration--success" />
        <span className="eyebrow">{t('report.received')}</span>
        <h1>{t('report.thanks')}</h1>
        <p>{t('report.municipalityReview')}</p>
        <div className="receipt-card">
          <span>{t('report.reportLabel')}</span>
          <strong>{result.ticketNumber}</strong>
          <span>{t('report.trackingCode')}</span>
          <strong className="tracking-code">{result.trackingCode}</strong>
          <CopyButton value={result.trackingCode} label={t('track.copyCode')} />
        </div>
        <div className="button-row">
          <Link className="button" to={`/track?trackingCode=${result.trackingCode}`}>
            {t('report.viewReport')}
          </Link>
          <Link className="button button-secondary" to="/history">
            {t('report.myReports')}
          </Link>
        </div>
      </section>
    );

  return (
    <section className="page page-enter report-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('report.eyebrow')}</span>
          <h1>{t('report.title')}</h1>
          <p className="lede">{t('report.lede')}</p>
        </div>
      </div>
      {restored ? <div className="notice notice-info">{t('report.draftRestored')}</div> : null}
      {profile && !profile.contributionReady ? (
        <div className="notice notice-error" role="alert">
          {t('report.notContributionReady')}
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
              ? t('report.validating')
              : phase === 'uploading'
                ? t('report.uploading')
                : t('report.submitting')}
          </span>
        </div>
      ) : null}
      <form className="report-grid" onSubmit={(event) => void submit(event)}>
        <div className="report-main settings-card">
          <h2 className="report-section-title">{t('report.stepDetails')}</h2>
          <label className="field-label" htmlFor="description">
            {t('report.describe')}
          </label>
          <textarea
            id="description"
            className="input textarea"
            maxLength={2000}
            placeholder={t('report.describePlaceholder')}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <span className="character-count">{description.length} / 2,000</span>
          <h2 className="report-section-title">{t('report.stepLocation')}</h2>
          <label className="sr-only" htmlFor="address">
            {t('report.location')}
          </label>
          <div className="location-row">
            <input
              id="address"
              className="input"
              placeholder={t('report.locationPlaceholder')}
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
              {t('report.check')}
            </button>
          </div>
          <button
            className={`location-button${locating ? ' location-button-loading' : ''}`}
            disabled={busy}
            type="button"
            onClick={() => void getDeviceLocation()}
          >
            <span aria-hidden className="location-button__mark">
              ⌖
            </span>
            <span>
              <strong>{locating ? t('report.validating') : t('report.useCurrent')}</strong>
              <small>{t('report.useCurrentHint')}</small>
            </span>
          </button>
          {location ? (
            <div className="validated-location">
              <span>✓</span>
              <div>
                <strong>{t('report.locationConfirmed')}</strong>
                <small>{location.addressText}</small>
              </div>
            </div>
          ) : null}
        </div>
        <div className="report-photo settings-card">
          <h2 className="report-section-title">{t('report.stepPhoto')}</h2>
          <label className="sr-only" htmlFor="photo">
            {t('report.photo')}
          </label>
          <label className="photo-drop" htmlFor="photo">
            {preview ? (
              <img src={preview} alt={t('report.photoAlt')} />
            ) : (
              <>
                <span className="photo-icon">＋</span>
                <strong>{t('report.choosePhoto')}</strong>
                <small>{t('report.photoHint')}</small>
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
                setError(t('report.photoTooLarge'));
                return;
              }
              setPhoto(file);
              setUploadedKey(undefined);
              if (preview) URL.revokeObjectURL(preview);
              setPreview(file ? URL.createObjectURL(file) : null);
            }}
          />
          {photoLabel ? <span className="helper">{photoLabel}</span> : null}
        </div>
        <section className="report-review settings-card" aria-labelledby="report-review-heading">
          <div className="review-summary">
            <h2 id="report-review-heading" className="report-section-title">
              {t('report.reviewHeading')}
            </h2>
            <div className={`review-item${description.trim() ? ' review-item-ready' : ''}`}>
              <span className="review-bullet" aria-hidden />
              <div>
                <strong>{t('report.describe')}</strong>
                <p>{description.trim() || t('report.describePlaceholder')}</p>
              </div>
            </div>
            <div className={`review-item${location ? ' review-item-ready' : ''}`}>
              <span className="review-bullet" aria-hidden />
              <div>
                <strong>{t('report.location')}</strong>
                <p>{location?.addressText || t('report.needLocation')}</p>
              </div>
            </div>
            <div className={`review-item${photoLabel ? ' review-item-ready' : ''}`}>
              <span className="review-bullet" aria-hidden />
              <div>
                <strong>{t('report.photo')}</strong>
                <p>{photoLabel || t('report.needPhoto')}</p>
              </div>
            </div>
          </div>
          <div className="privacy-callout">
            <span aria-hidden>◉</span>
            <p>
              <strong>{t('report.protected')}</strong>
              <br />
              {t('report.protectedBody')}
            </p>
          </div>
          <p className="helper" style={{ marginTop: '0.5rem' }}>
            {t('report.privacyJit')} <Link to="/privacy">{t('report.privacyJitLink')}</Link>
          </p>
          <button
            className="button button-large"
            disabled={busy || Boolean(profile && !profile.contributionReady)}
            type="submit"
          >
            {busy ? t('report.pleaseWait') : t('report.submit')} <span aria-hidden>→</span>
          </button>
          {!profile ? <p className="submit-sign-in-note">{t('report.signInAtSubmit')}</p> : null}
          <button
            className="text-button"
            disabled={busy}
            type="button"
            onClick={() => void discard()}
          >
            {t('report.discard')}
          </button>
        </section>
      </form>
    </section>
  );
}

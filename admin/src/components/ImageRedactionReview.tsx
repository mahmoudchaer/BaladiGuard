import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import type { ImageRedactionReview } from '@/types/ticket';
import { ImagePrivacyStatus } from '@/components/ImagePrivacyStatus';
import { TicketPhoto } from '@/components/TicketPhoto';
import {
  applyManualImageRedaction,
  approveImageRedaction,
  fetchImageRedactionReview,
  rejectImageRedaction,
  reprocessImageRedaction,
} from '@/services/tickets';
import { useI18n } from '@/i18n/LocaleProvider';
import './ImageRedactionReview.css';

type Props = {
  ticketId: string;
  category: string;
  onChanged?: () => void;
};

export function ImageRedactionReviewPanel({ ticketId, category, onChanged }: Props) {
  const { t } = useI18n();
  const [review, setReview] = useState<ImageRedactionReview | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [left, setLeft] = useState('0.10');
  const [top, setTop] = useState('0.10');
  const [width, setWidth] = useState('0.20');
  const [height, setHeight] = useState('0.20');

  useEffect(() => {
    let cancelled = false;
    setLoadError(null);
    void fetchImageRedactionReview(ticketId)
      .then((payload) => {
        if (!cancelled) {
          setReview(payload);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLoadError(error instanceof Error ? error.message : t('redaction.loadError'));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [ticketId, t]);

  async function runAction(action: () => Promise<ImageRedactionReview>) {
    setBusy(true);
    setActionError(null);
    try {
      const next = await action();
      setReview(next);
      onChanged?.();
    } catch (error: unknown) {
      setActionError(error instanceof Error ? error.message : t('redaction.actionError'));
    } finally {
      setBusy(false);
    }
  }

  function handleManualSubmit(event: FormEvent) {
    event.preventDefault();
    if (!review) {
      return;
    }
    const region = {
      left: Number(left),
      top: Number(top),
      width: Number(width),
      height: Number(height),
    };
    void runAction(() =>
      applyManualImageRedaction(review.ticketId, review.generation, review.candidateRevision, [
        region,
      ]),
    );
  }

  if (loadError) {
    return <p className="image-redaction-review__error">{loadError}</p>;
  }
  if (!review) {
    return <p className="image-redaction-review__hint">{t('redaction.loading')}</p>;
  }

  return (
    <div className="image-redaction-review">
      <div className="image-redaction-review__status">
        <ImagePrivacyStatus
          redaction={{
            status: review.status,
            generation: review.generation,
            faceCount: review.faceCount,
            plateCount: review.plateCount,
            reasonCode: review.reasonCode,
          }}
        />
        {review.reasonCode ? (
          <span className="image-redaction-review__reason">
            {t('redaction.reason', { code: review.reasonCode })}
          </span>
        ) : null}
      </div>

      <div className="image-redaction-review__pair">
        <div>
          <p className="image-redaction-review__label">{t('redaction.original')}</p>
          <TicketPhoto
            category={category}
            alt={t('redaction.originalAlt')}
            imageUrl={review.originalImageUrl ?? undefined}
          />
        </div>
        <div>
          <p className="image-redaction-review__label">{t('redaction.candidate')}</p>
          <TicketPhoto
            category={category}
            alt={t('redaction.candidateAlt')}
            imageUrl={review.candidateImageUrl ?? undefined}
          />
        </div>
      </div>

      {actionError ? <p className="image-redaction-review__error">{actionError}</p> : null}

      <div className="image-redaction-review__actions">
        <button
          type="button"
          className="ticket-detail__review-button"
          disabled={busy || !review.canApprove}
          onClick={() =>
            void runAction(() =>
              approveImageRedaction(ticketId, review.generation, review.candidateRevision),
            )
          }
        >
          {t('redaction.approve')}
        </button>
        <button
          type="button"
          className="ticket-detail__ghost-button"
          disabled={busy || !review.canReject}
          onClick={() =>
            void runAction(() =>
              rejectImageRedaction(ticketId, review.generation, review.candidateRevision),
            )
          }
        >
          {t('redaction.reject')}
        </button>
        <button
          type="button"
          className="ticket-detail__ghost-button"
          disabled={busy || !review.canReprocess}
          onClick={() => void runAction(() => reprocessImageRedaction(ticketId))}
        >
          {t('redaction.reprocess')}
        </button>
      </div>

      {review.canAddManualRegions ? (
        <form className="image-redaction-review__manual" onSubmit={handleManualSubmit}>
          <p className="image-redaction-review__label">{t('redaction.manualHint')}</p>
          <div className="image-redaction-review__fields">
            <label>
              {t('redaction.left')}
              <input value={left} onChange={(event) => setLeft(event.target.value)} />
            </label>
            <label>
              {t('redaction.top')}
              <input value={top} onChange={(event) => setTop(event.target.value)} />
            </label>
            <label>
              {t('redaction.width')}
              <input value={width} onChange={(event) => setWidth(event.target.value)} />
            </label>
            <label>
              {t('redaction.height')}
              <input value={height} onChange={(event) => setHeight(event.target.value)} />
            </label>
          </div>
          <button type="submit" className="ticket-detail__review-button" disabled={busy}>
            {t('redaction.applyManual')}
          </button>
        </form>
      ) : null}
    </div>
  );
}

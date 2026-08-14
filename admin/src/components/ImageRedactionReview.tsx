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
import './ImageRedactionReview.css';

type Props = {
  ticketId: string;
  category: string;
  onChanged?: () => void;
};

export function ImageRedactionReviewPanel({ ticketId, category, onChanged }: Props) {
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
          setLoadError(error instanceof Error ? error.message : 'Unable to load image review.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [ticketId]);

  async function runAction(action: () => Promise<ImageRedactionReview>) {
    setBusy(true);
    setActionError(null);
    try {
      const next = await action();
      setReview(next);
      onChanged?.();
    } catch (error: unknown) {
      setActionError(error instanceof Error ? error.message : 'Unable to update image review.');
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
    return <p className="image-redaction-review__hint">Loading image privacy review…</p>;
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
          <span className="image-redaction-review__reason">Reason: {review.reasonCode}</span>
        ) : null}
      </div>

      <div className="image-redaction-review__pair">
        <div>
          <p className="image-redaction-review__label">Original (staff only)</p>
          <TicketPhoto
            category={category}
            alt="Original private report photo"
            imageUrl={review.originalImageUrl ?? undefined}
          />
        </div>
        <div>
          <p className="image-redaction-review__label">Redacted candidate</p>
          <TicketPhoto
            category={category}
            alt="Redacted candidate photo"
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
          Approve public derivative
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
          Keep private only
        </button>
        <button
          type="button"
          className="ticket-detail__ghost-button"
          disabled={busy || !review.canReprocess}
          onClick={() => void runAction(() => reprocessImageRedaction(ticketId))}
        >
          Reprocess automatically
        </button>
      </div>

      {review.canAddManualRegions ? (
        <form className="image-redaction-review__manual" onSubmit={handleManualSubmit}>
          <p className="image-redaction-review__label">Add a bounded blur region (0–1 of image)</p>
          <div className="image-redaction-review__fields">
            <label>
              Left
              <input value={left} onChange={(event) => setLeft(event.target.value)} />
            </label>
            <label>
              Top
              <input value={top} onChange={(event) => setTop(event.target.value)} />
            </label>
            <label>
              Width
              <input value={width} onChange={(event) => setWidth(event.target.value)} />
            </label>
            <label>
              Height
              <input value={height} onChange={(event) => setHeight(event.target.value)} />
            </label>
          </div>
          <button type="submit" className="ticket-detail__review-button" disabled={busy}>
            Apply manual blur
          </button>
        </form>
      ) : null}
    </div>
  );
}

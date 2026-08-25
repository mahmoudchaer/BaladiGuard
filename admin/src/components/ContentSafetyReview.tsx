import { useEffect, useState } from 'react';
import type { ContentSafetyReview } from '@/types/ticket';
import { TicketPhoto } from '@/components/TicketPhoto';
import {
  approveContentSafety,
  fetchContentSafetyReview,
  markContentSafetyPrivate,
  rejectContentSafety,
  reprocessContentSafety,
} from '@/services/tickets';
import { useI18n } from '@/i18n/LocaleProvider';
import './ContentSafetyReview.css';

type Props = {
  ticketId: string;
  category: string;
  onChanged?: () => void;
};

export function ContentSafetyReviewPanel({ ticketId, category, onChanged }: Props) {
  const { t } = useI18n();
  const [review, setReview] = useState<ContentSafetyReview | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoadError(null);
    void fetchContentSafetyReview(ticketId)
      .then((payload) => {
        if (!cancelled) {
          setReview(payload);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLoadError(error instanceof Error ? error.message : t('contentSafety.loadError'));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [ticketId, t]);

  async function runAction(action: () => Promise<ContentSafetyReview>) {
    setBusy(true);
    setActionError(null);
    try {
      const next = await action();
      setReview(next);
      onChanged?.();
    } catch (error: unknown) {
      setActionError(error instanceof Error ? error.message : t('contentSafety.actionError'));
    } finally {
      setBusy(false);
    }
  }

  if (loadError) {
    return <p className="content-safety-review__error">{loadError}</p>;
  }
  if (!review) {
    return <p className="content-safety-review__hint">{t('contentSafety.loading')}</p>;
  }

  const statusKey = `contentSafety.status.${review.status}` as const;
  const authenticity = review.authenticityScore;
  const authenticityLabel =
    authenticity == null
      ? t('contentSafety.authenticityUnavailable')
      : t('contentSafety.authenticityScore', { score: authenticity.toFixed(2) });

  return (
    <div className="content-safety-review">
      <div className="content-safety-review__status">
        <span
          className={`content-safety-review__badge content-safety-review__badge--${review.status}`}
        >
          {t(statusKey)}
        </span>
        {review.reasonCode ? (
          <span className="content-safety-review__reason">
            {t('contentSafety.reason', { code: review.reasonCode })}
          </span>
        ) : null}
      </div>
      <p className="content-safety-review__hint">{authenticityLabel}</p>
      {review.authenticitySignals.length > 0 ? (
        <p className="content-safety-review__signals">
          {t('contentSafety.signals', { codes: review.authenticitySignals.join(', ') })}
        </p>
      ) : null}
      {review.imageLabels.length > 0 ? (
        <p className="content-safety-review__signals">
          {t('contentSafety.imageLabels', { codes: review.imageLabels.join(', ') })}
        </p>
      ) : null}
      {review.staffNote ? (
        <p className="content-safety-review__signals">
          {t('contentSafety.savedNote', { note: review.staffNote })}
        </p>
      ) : null}

      {review.originalImageUrl ? (
        <div>
          <p className="content-safety-review__label">{t('contentSafety.original')}</p>
          <TicketPhoto
            category={category}
            alt={t('contentSafety.originalAlt')}
            imageUrl={review.originalImageUrl}
          />
        </div>
      ) : null}

      {review.canApprove || review.canReject || review.canMarkPrivate ? (
        <label className="content-safety-review__note">
          <span className="content-safety-review__label">{t('contentSafety.note')}</span>
          <textarea
            className="content-safety-review__note-input"
            maxLength={500}
            rows={3}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder={t('contentSafety.notePlaceholder')}
            disabled={busy}
          />
        </label>
      ) : null}

      {actionError ? <p className="content-safety-review__error">{actionError}</p> : null}

      <div className="content-safety-review__actions">
        <button
          type="button"
          className="ticket-detail__review-button"
          disabled={busy || !review.canApprove}
          onClick={() =>
            void runAction(() =>
              approveContentSafety(ticketId, review.generation, note.trim() || undefined),
            )
          }
        >
          {t('contentSafety.approve')}
        </button>
        <button
          type="button"
          className="ticket-detail__ghost-button"
          disabled={busy || !review.canMarkPrivate}
          onClick={() => {
            if (!window.confirm(t('contentSafety.confirmPrivate'))) {
              return;
            }
            void runAction(() =>
              markContentSafetyPrivate(
                ticketId,
                review.generation,
                'STAFF_PRIVATE_ONLY',
                note.trim() || undefined,
              ),
            );
          }}
        >
          {t('contentSafety.privateOnly')}
        </button>
        <button
          type="button"
          className="ticket-detail__ghost-button"
          disabled={busy || !review.canReject}
          onClick={() => {
            if (!window.confirm(t('contentSafety.confirmReject'))) {
              return;
            }
            void runAction(() =>
              rejectContentSafety(
                ticketId,
                review.generation,
                'STAFF_REJECTED',
                note.trim() || undefined,
              ),
            );
          }}
        >
          {t('contentSafety.reject')}
        </button>
        <button
          type="button"
          className="ticket-detail__ghost-button"
          disabled={busy || !review.canReprocess}
          onClick={() => void runAction(() => reprocessContentSafety(ticketId))}
        >
          {t('contentSafety.reprocess')}
        </button>
      </div>
    </div>
  );
}

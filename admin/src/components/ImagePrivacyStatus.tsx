import type { TicketImageRedaction } from '@/types/ticket';

import './ImagePrivacyStatus.css';

type Props = {
  redaction?: TicketImageRedaction;
};

const LABELS: Record<TicketImageRedaction['status'], string> = {
  pending: 'Waiting for privacy processing',
  processing: 'Privacy processing in progress',
  completed: 'Public derivative is privacy-safe',
  failed: 'Processing failed — original remains private',
  review_required: 'Review required — original remains private',
};

export function ImagePrivacyStatus({ redaction }: Props) {
  const status = redaction?.status ?? 'pending';
  return (
    <div className={`image-privacy image-privacy--${status}`} role="status">
      <span className="image-privacy__label">{LABELS[status]}</span>
      {status === 'completed' && redaction ? (
        <span className="image-privacy__detail">
          {redaction.faceCount} face(s) and {redaction.plateCount} plate(s) redacted
        </span>
      ) : null}
    </div>
  );
}

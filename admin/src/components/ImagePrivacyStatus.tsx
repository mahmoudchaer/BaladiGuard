import { t } from '@/i18n';
import type { TicketImageRedaction } from '@/types/ticket';

import './ImagePrivacyStatus.css';

type Props = {
  redaction?: TicketImageRedaction;
};

export function ImagePrivacyStatus({ redaction }: Props) {
  const status = redaction?.status ?? 'pending';
  return (
    <div className={`image-privacy image-privacy--${status}`} role="status">
      <span className="image-privacy__label">{t(`redaction.${status}`)}</span>
      {status === 'completed' && redaction ? (
        <span className="image-privacy__detail">
          {t('redaction.facesPlates', {
            faces: redaction.faceCount,
            plates: redaction.plateCount,
          })}
        </span>
      ) : null}
    </div>
  );
}

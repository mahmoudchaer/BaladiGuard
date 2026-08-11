import { useState } from 'react';
import { config } from '@/services/config';
import { formatCategory } from '@/utils/labels';
import { getTicketImageUrl } from '@/utils/ticketImage';
import { IconImage } from '@/components/icons';
import './TicketPhoto.css';

type TicketPhotoProps = {
  imageObjectKey: string;
  category: string;
  alt: string;
  imageUrl?: string;
  /**
   * Raw storage keys are technical metadata, so they stay hidden unless a
   * surface explicitly needs them (e.g. a technical-details disclosure).
   */
  showObjectKey?: boolean;
};

export function TicketPhoto({
  imageObjectKey,
  category,
  alt,
  imageUrl,
  showObjectKey = false,
}: TicketPhotoProps) {
  const [hasError, setHasError] = useState(false);
  const categorySlug = category.replace(/_/g, '-');

  if (config.useMockData) {
    return (
      <figure className={`ticket-photo ticket-photo--mock ticket-photo--${categorySlug}`}>
        <div className="ticket-photo__mock" role="img" aria-label={alt}>
          <div className="ticket-photo__mock-flag" aria-hidden="true" />
          <IconImage className="ticket-photo__mock-icon" />
          <span className="ticket-photo__mock-category">{formatCategory(category)}</span>
          <span className="ticket-photo__mock-hint">Citizen report photograph</span>
        </div>
        {showObjectKey && (
          <figcaption className="ticket-photo__caption">{imageObjectKey}</figcaption>
        )}
      </figure>
    );
  }

  const resolvedImageUrl = getTicketImageUrl(imageObjectKey, category, imageUrl);

  if (!resolvedImageUrl || hasError) {
    return (
      <figure className="ticket-photo ticket-photo--fallback">
        <div className="ticket-photo__fallback" role="img" aria-label={alt}>
          <IconImage className="ticket-photo__fallback-icon" />
          <p className="ticket-photo__fallback-title">Report photo unavailable</p>
          {showObjectKey && <p className="ticket-photo__fallback-key">{imageObjectKey}</p>}
        </div>
      </figure>
    );
  }

  return (
    <figure className="ticket-photo">
      <img
        className="ticket-photo__image"
        src={resolvedImageUrl}
        alt={alt}
        onError={() => setHasError(true)}
      />
      {showObjectKey && <figcaption className="ticket-photo__caption">{imageObjectKey}</figcaption>}
    </figure>
  );
}

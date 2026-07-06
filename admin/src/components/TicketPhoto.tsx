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
};

export function TicketPhoto({ imageObjectKey, category, alt }: TicketPhotoProps) {
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
        <figcaption className="ticket-photo__caption">{imageObjectKey}</figcaption>
      </figure>
    );
  }

  const imageUrl = getTicketImageUrl(imageObjectKey, category);

  if (hasError) {
    return (
      <figure className="ticket-photo ticket-photo--fallback">
        <div className="ticket-photo__fallback" role="img" aria-label={alt}>
          <IconImage className="ticket-photo__fallback-icon" />
          <p className="ticket-photo__fallback-title">Report photo unavailable</p>
          <p className="ticket-photo__fallback-key">{imageObjectKey}</p>
        </div>
      </figure>
    );
  }

  return (
    <figure className="ticket-photo">
      <img
        className="ticket-photo__image"
        src={imageUrl}
        alt={alt}
        onError={() => setHasError(true)}
      />
      <figcaption className="ticket-photo__caption">{imageObjectKey}</figcaption>
    </figure>
  );
}

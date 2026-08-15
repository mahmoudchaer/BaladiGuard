import { useState } from 'react';
import { t } from '@/i18n';

type PublicPhotoProps = {
  photoUrl?: string | null;
  alt: string;
};

/** Fail closed: missing or broken public URLs become a placeholder (#263 / #253). */
export function PublicPhoto({ photoUrl, alt }: PublicPhotoProps) {
  const [failed, setFailed] = useState(false);
  const usable = Boolean(photoUrl) && !failed;

  if (!usable) {
    return (
      <div className="photo-fallback" role="img" aria-label={t('public.noPhoto')}>
        {t('public.photoUnavailable')}
      </div>
    );
  }

  return (
    <img
      className="photo"
      src={photoUrl!}
      alt={alt}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}

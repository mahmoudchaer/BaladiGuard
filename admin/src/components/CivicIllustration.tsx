import cedarLocation from '@/assets/illustrations/cedar-location.webp';
import lebanonMap from '@/assets/illustrations/lebanon-service-map.webp';
import municipalWorker from '@/assets/illustrations/municipal-worker.webp';
import reportClipboard from '@/assets/illustrations/report-clipboard.webp';
import searchEmpty from '@/assets/illustrations/search-empty.webp';
import './CivicIllustration.css';

export type AdminIllustrationName = 'tickets' | 'map' | 'workforce' | 'operations' | 'search';

const sources: Record<AdminIllustrationName, string> = {
  tickets: reportClipboard,
  map: lebanonMap,
  workforce: municipalWorker,
  operations: cedarLocation,
  search: searchEmpty,
};

type Props = { name: AdminIllustrationName; className?: string; priority?: boolean };

export function CivicIllustration({ name, className = '', priority = false }: Props) {
  return (
    <img
      alt=""
      aria-hidden="true"
      className={`admin-civic-illustration ${className}`.trim()}
      decoding="async"
      loading={priority ? 'eager' : 'lazy'}
      src={sources[name]}
    />
  );
}

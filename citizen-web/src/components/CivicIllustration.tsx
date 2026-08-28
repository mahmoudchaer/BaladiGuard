import './CivicIllustration.css';

export type CivicIllustrationName =
  | 'citizen-reporting'
  | 'municipal-worker'
  | 'lebanon-service-map'
  | 'report-clipboard'
  | 'report-resolved'
  | 'cedar-location'
  | 'community-contribution'
  | 'privacy-verified'
  | 'search-empty';

type Props = {
  name: CivicIllustrationName;
  className?: string;
  priority?: boolean;
};

export function CivicIllustration({ name, className = '', priority = false }: Props) {
  return (
    <img
      alt=""
      aria-hidden="true"
      className={`civic-illustration civic-illustration--${name} ${className}`.trim()}
      decoding="async"
      loading={priority ? 'eager' : 'lazy'}
      src={`/illustrations/${name}.webp`}
    />
  );
}

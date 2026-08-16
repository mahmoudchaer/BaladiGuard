import { getLocale, t } from '@/i18n';
import type { TicketStatus, TicketPriority } from '@/types/ticket';

const CATEGORY_LABELS: Record<string, string> = {
  road_damage: 'Road Damage',
  street_lighting: 'Street Lighting',
  waste: 'Waste',
  water_leak: 'Water Leak',
  sidewalk_damage: 'Sidewalk Damage',
  drainage: 'Drainage',
  noise: 'Noise',
  traffic_signal: 'Traffic Signal',
  public_facilities: 'Public Facilities',
  PENDING_CLASSIFICATION: 'Pending Classification',
};

export const SUPPORTED_CATEGORY_OPTIONS = [
  'road_damage',
  'waste',
  'street_lighting',
  'water_leak',
  'noise',
  'sidewalk_damage',
  'traffic_signal',
  'drainage',
  'public_facilities',
] as const;

export function formatStatus(status: TicketStatus): string {
  const translated = t(`status.${status}`);
  return translated !== `status.${status}` ? translated : status;
}

export function formatPriority(priority: TicketPriority | null): string {
  if (!priority) {
    return t('priority.unrated');
  }
  const translated = t(`priority.${priority}`);
  return translated !== `priority.${priority}` ? translated : priority;
}

export function formatCategory(category: string): string {
  const translated = t(`category.${category}`);
  if (translated !== `category.${category}`) {
    return translated;
  }
  if (CATEGORY_LABELS[category]) {
    return CATEGORY_LABELS[category];
  }
  return category
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export function formatCreatedDate(isoDate: string): string {
  return new Intl.DateTimeFormat(getLocale(), {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(isoDate));
}

/** Compact age label for operational scanning (e.g. "2h", "3d"). */
export function formatTicketAge(isoDate: string, now = Date.now()): string {
  const createdAt = Date.parse(isoDate);
  if (!Number.isFinite(createdAt)) {
    return '—';
  }

  const elapsedMs = Math.max(0, now - createdAt);
  const minutes = Math.floor(elapsedMs / (60 * 1000));
  if (minutes < 60) {
    return `${Math.max(1, minutes)}m`;
  }

  const hours = Math.floor(minutes / 60);
  if (hours < 48) {
    return `${hours}h`;
  }

  const days = Math.floor(hours / 24);
  return `${days}d`;
}

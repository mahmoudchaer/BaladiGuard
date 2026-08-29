import { t } from '@/i18n';
import type { TicketStatus } from '@/types/ticket';

export const categoryLabels: Record<string, string> = {
  road_damage: 'Road Damage',
  waste: 'Waste',
  street_lighting: 'Street Lighting',
  water_leak: 'Water Leak',
  noise: 'Noise',
  sidewalk_damage: 'Sidewalk Damage',
  traffic_signal: 'Traffic Signal',
  drainage: 'Drainage',
  public_facilities: 'Public Facilities',
};

export const statusLabels: Record<TicketStatus, string> = {
  SUBMITTED: 'Submitted',
  UNDER_REVIEW: 'Under Review',
  ASSIGNED: 'Assigned',
  IN_PROGRESS: 'In Progress',
  RESOLVED: 'Resolved',
  CLOSED: 'Closed',
};

/** Title-cases an unrecognized `snake_case` category as a readable fallback. */
function titleCaseFallback(normalized: string): string {
  return normalized
    .split('_')
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(' ');
}

export function formatCategoryLabel(category: string | null | undefined): string {
  if (!category) {
    return t('status.pendingCategory');
  }
  const normalized = category.toLowerCase();
  if (normalized === 'pending_classification') {
    return t('status.pendingCategory');
  }
  const translated = t(`category.${normalized}`);
  if (translated !== `category.${normalized}`) {
    return translated;
  }
  return categoryLabels[normalized] ?? titleCaseFallback(normalized);
}

export function formatStatusLabel(status: TicketStatus): string {
  const translated = t(`status.${status}`);
  return translated !== `status.${status}` ? translated : (statusLabels[status] ?? status);
}

/** Short, plain-language description of what a status means for a citizen. */
export function describeStatusMeaning(status: TicketStatus): string {
  switch (status) {
    case 'SUBMITTED':
      return t('statusMeaning.SUBMITTED');
    case 'UNDER_REVIEW':
      return t('statusMeaning.UNDER_REVIEW');
    case 'ASSIGNED':
      return t('statusMeaning.ASSIGNED');
    case 'IN_PROGRESS':
      return t('statusMeaning.IN_PROGRESS');
    case 'RESOLVED':
      return t('statusMeaning.RESOLVED');
    case 'CLOSED':
      return t('statusMeaning.CLOSED');
    default:
      return t('statusMeaning.unknown');
  }
}

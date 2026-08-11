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
    return 'Category pending';
  }
  const normalized = category.toLowerCase();
  if (normalized === 'pending_classification') {
    return 'Category pending';
  }
  return categoryLabels[normalized] ?? titleCaseFallback(normalized);
}

export function formatStatusLabel(status: TicketStatus): string {
  return statusLabels[status] ?? status;
}

/** Short, plain-language description of what a status means for a citizen. */
export function describeStatusMeaning(status: TicketStatus): string {
  switch (status) {
    case 'SUBMITTED':
      return 'Your report was received and is in the queue for review.';
    case 'UNDER_REVIEW':
      return 'A staff member is reviewing the report before it is routed.';
    case 'ASSIGNED':
      return 'A department has taken ownership of this report.';
    case 'IN_PROGRESS':
      return 'The assigned team is actively working on the issue.';
    case 'RESOLVED':
      return 'The issue has been marked resolved.';
    case 'CLOSED':
      return 'This report has been closed.';
    default:
      return 'Status details are not available right now.';
  }
}

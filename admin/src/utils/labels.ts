import type { TicketStatus, TicketPriority } from '@/types/ticket';

const STATUS_LABELS: Record<TicketStatus, string> = {
  SUBMITTED: 'Submitted',
  UNDER_REVIEW: 'Under Review',
  ASSIGNED: 'Assigned',
  IN_PROGRESS: 'In Progress',
  RESOLVED: 'Resolved',
};

const PRIORITY_LABELS: Record<TicketPriority, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
};

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

export function formatStatus(status: TicketStatus): string {
  return STATUS_LABELS[status] ?? status;
}

export function formatPriority(priority: TicketPriority | null): string {
  if (!priority) {
    return 'Unrated';
  }
  return PRIORITY_LABELS[priority] ?? priority;
}

export function formatCategory(category: string): string {
  if (CATEGORY_LABELS[category]) {
    return CATEGORY_LABELS[category];
  }
  return category
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export function formatCreatedDate(isoDate: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(isoDate));
}

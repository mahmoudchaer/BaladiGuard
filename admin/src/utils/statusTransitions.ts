import type { TicketStatus } from '@/types/ticket';

const ALLOWED_STATUS_TRANSITIONS: Record<TicketStatus, TicketStatus[]> = {
  SUBMITTED: ['UNDER_REVIEW', 'CLOSED'],
  UNDER_REVIEW: ['ASSIGNED', 'CLOSED'],
  ASSIGNED: ['IN_PROGRESS', 'UNDER_REVIEW'],
  IN_PROGRESS: ['RESOLVED', 'ASSIGNED'],
  RESOLVED: ['CLOSED', 'IN_PROGRESS'],
  CLOSED: [],
};

export function getSelectableTicketStatuses(currentStatus: TicketStatus): TicketStatus[] {
  return [currentStatus, ...ALLOWED_STATUS_TRANSITIONS[currentStatus]];
}

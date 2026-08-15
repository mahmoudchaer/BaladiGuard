import type { TicketStatus } from '@/types/ticket';

export type OutcomeKind = 'resolution' | 'rejection' | 'closure';

export const RESOLUTION_REASONS = [
  { code: 'WORK_COMPLETED', label: 'Work completed as requested' },
  { code: 'TEMPORARY_FIX', label: 'Temporary repair applied' },
  { code: 'NO_WORK_REQUIRED', label: 'No municipal work required' },
  { code: 'REFERRED_EXTERNAL', label: 'Referred to another authority' },
  { code: 'DUPLICATE_RESOLVED', label: 'Resolved as a duplicate' },
] as const;

export const REJECTION_REASONS = [
  { code: 'OUT_OF_SCOPE', label: 'Outside municipal responsibility' },
  { code: 'INSUFFICIENT_INFORMATION', label: 'Insufficient information' },
  { code: 'DUPLICATE', label: 'Duplicate of an existing report' },
  { code: 'INVALID_REPORT', label: 'Not a valid municipal issue' },
  { code: 'CITIZEN_WITHDRAWN', label: 'Citizen withdrew the report' },
  { code: 'SPAM', label: 'Spam or abusive report' },
] as const;

export const CLOSURE_REASONS = [
  { code: 'CONFIRMED_COMPLETE', label: 'Resolution confirmed, case closed' },
  { code: 'ADMINISTRATIVE_CLOSE', label: 'Closed after resolution for records' },
  { code: 'NO_FURTHER_ACTION', label: 'No further municipal action' },
] as const;

export const WORK_ORDER_CANCEL_REASONS = [
  { code: 'CREATED_IN_ERROR', label: 'Created in error' },
  { code: 'NO_LONGER_NEEDED', label: 'No longer needed' },
  { code: 'UNABLE_TO_PERFORM', label: 'Unable to perform the work' },
  { code: 'DUPLICATE_WORK', label: 'Duplicate work order' },
] as const;

export function requiredOutcomeKind(
  currentStatus: TicketStatus,
  requestedStatus: TicketStatus,
): OutcomeKind | null {
  if (requestedStatus === 'RESOLVED') {
    return 'resolution';
  }
  if (requestedStatus !== 'CLOSED') {
    return null;
  }
  if (currentStatus === 'RESOLVED') {
    return 'closure';
  }
  if (currentStatus === 'SUBMITTED' || currentStatus === 'UNDER_REVIEW') {
    return 'rejection';
  }
  return null;
}

export function reasonsForKind(kind: OutcomeKind) {
  if (kind === 'resolution') {
    return RESOLUTION_REASONS;
  }
  if (kind === 'rejection') {
    return REJECTION_REASONS;
  }
  return CLOSURE_REASONS;
}

export function formatWorkOrderState(state: string): string {
  switch (state) {
    case 'QUEUED':
      return 'Queued';
    case 'ASSIGNED':
      return 'Assigned';
    case 'IN_PROGRESS':
      return 'In progress';
    case 'COMPLETED':
      return 'Completed';
    case 'CANCELLED':
      return 'Cancelled';
    default:
      return state;
  }
}

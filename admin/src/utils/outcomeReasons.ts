import { t } from '@/i18n';
import type { TicketStatus } from '@/types/ticket';

export type OutcomeKind = 'resolution' | 'rejection' | 'closure';

export const RESOLUTION_REASONS = [
  { code: 'WORK_COMPLETED' },
  { code: 'TEMPORARY_FIX' },
  { code: 'NO_WORK_REQUIRED' },
  { code: 'REFERRED_EXTERNAL' },
  { code: 'DUPLICATE_RESOLVED' },
] as const;

export const REJECTION_REASONS = [
  { code: 'OUT_OF_SCOPE' },
  { code: 'INSUFFICIENT_INFORMATION' },
  { code: 'DUPLICATE' },
  { code: 'INVALID_REPORT' },
  { code: 'CITIZEN_WITHDRAWN' },
  { code: 'SPAM' },
] as const;

export const CLOSURE_REASONS = [
  { code: 'CONFIRMED_COMPLETE' },
  { code: 'ADMINISTRATIVE_CLOSE' },
  { code: 'NO_FURTHER_ACTION' },
] as const;

export const WORK_ORDER_CANCEL_REASONS = [
  { code: 'CREATED_IN_ERROR' },
  { code: 'NO_LONGER_NEEDED' },
  { code: 'UNABLE_TO_PERFORM' },
  { code: 'DUPLICATE_WORK' },
] as const;

function withReasonLabel<T extends { code: string }>(reason: T): T & { label: string } {
  return { ...reason, label: t(`reasons.${reason.code}`) };
}

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
    return RESOLUTION_REASONS.map(withReasonLabel);
  }
  if (kind === 'rejection') {
    return REJECTION_REASONS.map(withReasonLabel);
  }
  return CLOSURE_REASONS.map(withReasonLabel);
}

export function workOrderCancelReasons() {
  return WORK_ORDER_CANCEL_REASONS.map(withReasonLabel);
}

export function formatWorkOrderState(state: string): string {
  const translated = t(`reasons.workOrder.${state}`);
  return translated !== `reasons.workOrder.${state}` ? translated : state;
}

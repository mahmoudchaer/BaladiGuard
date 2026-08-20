import type { Ticket, TicketAuditActionType, TicketStatus } from '@/types/ticket';
import { formatStatus } from '@/utils/labels';
import { normalizeTimelineEvents } from '@/utils/timeline';

export type ActivityEventKind = 'created' | 'status' | 'audit';

export type ActivityEvent = {
  id: string;
  kind: ActivityEventKind;
  occurredAt: string;
  title: string;
  status?: TicketStatus;
  actor?: string;
  detail?: string;
  change?: string;
};

const AUDIT_ACTION_LABELS: Record<TicketAuditActionType, string> = {
  STATUS_CHANGE: 'Status change',
  CATEGORY_REVIEW: 'Category review',
  DEPARTMENT_ASSIGN: 'Department assignment',
  DUPLICATE_MERGE: 'Duplicate merge',
  PUBLIC_CONTENT_UPDATE: 'Public content update',
  STAFF_COMMENT: 'Staff comment',
  IMAGE_REDACTION_APPROVE: 'Image redaction approved',
  IMAGE_REDACTION_REJECT: 'Image kept private-only',
  IMAGE_REDACTION_REPROCESS: 'Image reprocessing requested',
  IMAGE_REDACTION_MANUAL_BLUR: 'Manual blur regions added',
  CONTENT_SAFETY_APPROVE: 'Content safety approved for public eligibility',
  CONTENT_SAFETY_REJECT: 'Content safety rejected as unsafe',
  CONTENT_SAFETY_PRIVATE_ONLY: 'Content safety marked private-only',
  CONTENT_SAFETY_REPROCESS: 'Content safety reprocessing requested',
  WORKFORCE_ASSIGN: 'Workforce assignment',
  WORK_ORDER_CREATE: 'Work order created',
  WORK_ORDER_ASSIGN: 'Work order assignment',
  WORK_ORDER_START: 'Work order started',
  WORK_ORDER_COMPLETE: 'Work order completed',
  WORK_ORDER_CANCEL: 'Work order cancelled',
  WORK_ORDER_EVIDENCE_ADD: 'Maintenance evidence added',
  RESOLUTION_FEEDBACK_SUBMIT: 'Citizen resolution feedback',
  RESOLUTION_FEEDBACK_REVIEW: 'Resolution feedback reviewed',
};

export function formatAuditAction(actionType: TicketAuditActionType): string {
  return AUDIT_ACTION_LABELS[actionType] ?? actionType;
}

function isUsableTimestamp(value: string | null | undefined): value is string {
  return typeof value === 'string' && value.length > 0 && !Number.isNaN(Date.parse(value));
}

/**
 * Merge submission, status history, and staff audit rows into one operational
 * timeline (newest first) so the workspace never repeats history in several
 * places. Malformed rows are skipped rather than failing the whole section.
 */
export function buildActivityTimeline(ticket: Ticket | null): ActivityEvent[] {
  if (!ticket) {
    return [];
  }

  const ordered: { event: ActivityEvent; order: number }[] = [];
  let order = 0;

  if (isUsableTimestamp(ticket.createdAt)) {
    ordered.push({
      event: {
        id: 'created',
        kind: 'created',
        occurredAt: ticket.createdAt,
        title: 'Report submitted by citizen',
        detail: ticket.location.addressText || undefined,
      },
      order: order++,
    });
  }

  const statusEvents = normalizeTimelineEvents(ticket.statusHistory);
  const statusTimestamps = new Set(statusEvents.map((event) => event.changedAt));

  for (const [index, event] of statusEvents.entries()) {
    ordered.push({
      event: {
        id: `status-${index}-${event.changedAt}`,
        kind: 'status',
        occurredAt: event.changedAt,
        title: `Status set to ${formatStatus(event.status)}`,
        status: event.status,
        actor: event.changedBy,
        detail: event.note,
      },
      order: order++,
    });
  }

  for (const [index, entry] of (ticket.auditHistory ?? []).entries()) {
    if (!entry || !isUsableTimestamp(entry.changedAt)) {
      continue;
    }
    // Status transitions already appear from statusHistory; skip the audit twin.
    if (entry.actionType === 'STATUS_CHANGE' && statusTimestamps.has(entry.changedAt)) {
      continue;
    }

    const change =
      entry.previousValue && entry.newValue
        ? `${entry.previousValue} → ${entry.newValue}`
        : (entry.newValue ?? undefined);

    ordered.push({
      event: {
        id: `audit-${index}-${entry.changedAt}`,
        kind: 'audit',
        occurredAt: entry.changedAt,
        title: formatAuditAction(entry.actionType),
        actor: entry.actorId,
        detail: entry.summary || undefined,
        change,
      },
      order: order++,
    });
  }

  return ordered
    .sort((a, b) => {
      const delta = Date.parse(b.event.occurredAt) - Date.parse(a.event.occurredAt);
      return delta !== 0 ? delta : b.order - a.order;
    })
    .map((item) => item.event);
}

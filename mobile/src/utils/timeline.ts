import type { TicketStatus, TicketStatusHistoryEntry } from '@/types/ticket';

export type NormalizedTimelineEvent = {
  status: TicketStatus;
  changedAt: string;
  changedBy?: string;
  note?: string;
};

/**
 * Filter malformed entries and return a deterministic chronological order
 * (oldest → newest). Equal timestamps keep their original relative order.
 */
export function normalizeTimelineEvents(
  history?: TicketStatusHistoryEntry[] | null,
): NormalizedTimelineEvent[] {
  if (!Array.isArray(history) || history.length === 0) {
    return [];
  }

  const valid = history.flatMap((entry, index) => {
    if (!entry || typeof entry !== 'object') {
      return [];
    }

    const status = entry.status;
    const changedAt = typeof entry.changedAt === 'string' ? entry.changedAt.trim() : '';
    if (
      status !== 'SUBMITTED' &&
      status !== 'UNDER_REVIEW' &&
      status !== 'ASSIGNED' &&
      status !== 'IN_PROGRESS' &&
      status !== 'RESOLVED' &&
      status !== 'CLOSED'
    ) {
      return [];
    }
    if (!changedAt || Number.isNaN(Date.parse(changedAt))) {
      return [];
    }

    return [
      {
        status,
        changedAt,
        index,
        changedBy:
          typeof entry.changedBy === 'string' && entry.changedBy.trim().length > 0
            ? entry.changedBy.trim()
            : undefined,
        note:
          typeof entry.note === 'string' && entry.note.trim().length > 0
            ? entry.note.trim()
            : undefined,
      },
    ];
  });

  return valid
    .sort((a, b) => {
      const delta = Date.parse(a.changedAt) - Date.parse(b.changedAt);
      return delta !== 0 ? delta : a.index - b.index;
    })
    .map((item) => ({
      status: item.status,
      changedAt: item.changedAt,
      ...(item.changedBy ? { changedBy: item.changedBy } : {}),
      ...(item.note ? { note: item.note } : {}),
    }));
}

import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';

import type { TicketStatus, TicketStatusHistoryEntry } from '@/types/ticket';
import { normalizeTimelineEvents } from '@/utils/timeline';

export type TicketTimelineVariant = 'staff' | 'citizen';

export type TicketTimelineProps = {
  history?: TicketStatusHistoryEntry[] | null;
  /** Staff view shows actor details; citizen view hides them. */
  variant?: TicketTimelineVariant;
  emptyMessage?: string;
};

const STATUS_LABELS: Record<TicketStatus, string> = {
  SUBMITTED: 'Submitted',
  UNDER_REVIEW: 'Under Review',
  ASSIGNED: 'Assigned',
  IN_PROGRESS: 'In Progress',
  RESOLVED: 'Resolved',
  CLOSED: 'Closed',
};

function formatTimelineDate(isoDate: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(isoDate));
}

export function TicketTimeline({
  history,
  variant = 'citizen',
  emptyMessage = 'No status history is available for this ticket yet.',
}: TicketTimelineProps) {
  const events = normalizeTimelineEvents(history);
  const showActor = variant === 'staff';

  if (events.length === 0) {
    return (
      <Text variant="bodyMedium" style={styles.empty}>
        {emptyMessage}
      </Text>
    );
  }

  return (
    <View accessibilityLabel="Ticket status timeline" style={styles.list}>
      {events.map((event, index) => {
        const isLatest = index === events.length - 1;
        return (
          <View
            key={`${event.changedAt}-${event.status}-${index}`}
            style={[styles.item, isLatest ? styles.itemLatest : null]}
          >
            <View style={[styles.marker, isLatest ? styles.markerLatest : null]} />
            <View style={styles.content}>
              <Text variant="titleSmall" style={styles.status}>
                {STATUS_LABELS[event.status] ?? event.status}
              </Text>
              <Text variant="bodySmall" style={styles.time}>
                {formatTimelineDate(event.changedAt)}
              </Text>
              {showActor && event.changedBy ? (
                <Text variant="bodySmall" style={styles.meta}>
                  Updated by {event.changedBy}
                </Text>
              ) : null}
              {event.note ? (
                <Text variant="bodySmall" style={styles.note}>
                  {event.note}
                </Text>
              ) : null}
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  list: {
    gap: 12,
  },
  item: {
    flexDirection: 'row',
    gap: 12,
    alignItems: 'flex-start',
  },
  itemLatest: {},
  marker: {
    width: 12,
    height: 12,
    marginTop: 4,
    borderRadius: 999,
    borderWidth: 2,
    borderColor: '#94A3B8',
    backgroundColor: '#FFFFFF',
  },
  markerLatest: {
    borderColor: '#0F766E',
    backgroundColor: '#0F766E',
  },
  content: {
    flex: 1,
    gap: 2,
  },
  status: {
    fontWeight: '700',
    color: '#0F172A',
  },
  time: {
    color: '#64748B',
  },
  meta: {
    color: '#475569',
  },
  note: {
    color: '#475569',
    fontStyle: 'italic',
  },
  empty: {
    color: '#64748B',
  },
});

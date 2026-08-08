import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';

import { colors, radii, spacing, typography } from '@/theme';
import { formatStatusLabel } from '@/theme/labels';
import type { TicketStatusHistoryEntry } from '@/types/ticket';
import { normalizeTimelineEvents } from '@/utils/timeline';

export type TicketTimelineVariant = 'staff' | 'citizen';

export type TicketTimelineProps = {
  history?: TicketStatusHistoryEntry[] | null;
  /**
   * Staff view shows actor and notes.
   * Citizen view is status + timestamp only (hides staff-only actor/notes).
   */
  variant?: TicketTimelineVariant;
  emptyMessage?: string;
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
  const showStaffDetails = variant === 'staff';

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
                {formatStatusLabel(event.status)}
              </Text>
              <Text variant="bodySmall" style={styles.time}>
                {formatTimelineDate(event.changedAt)}
              </Text>
              {showStaffDetails && event.changedBy ? (
                <Text variant="bodySmall" style={styles.meta}>
                  Updated by {event.changedBy}
                </Text>
              ) : null}
              {showStaffDetails && event.note ? (
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
    gap: spacing[3],
  },
  item: {
    flexDirection: 'row',
    gap: spacing[3],
    alignItems: 'flex-start',
  },
  itemLatest: {},
  marker: {
    width: 12,
    height: 12,
    marginTop: 4,
    borderRadius: radii.pill,
    borderWidth: 2,
    borderColor: colors.borderStrong,
    backgroundColor: colors.surface,
  },
  markerLatest: {
    borderColor: colors.brand,
    backgroundColor: colors.brand,
  },
  content: {
    flex: 1,
    gap: 2,
  },
  status: {
    fontWeight: '700',
    color: colors.text,
    fontSize: typography.bodyCompact,
  },
  time: {
    color: colors.textMuted,
    fontSize: typography.metadata,
  },
  meta: {
    color: colors.textSecondary,
    fontSize: typography.metadata,
  },
  note: {
    color: colors.textSecondary,
    fontSize: typography.metadata,
    fontStyle: 'italic',
  },
  empty: {
    color: colors.textMuted,
  },
});

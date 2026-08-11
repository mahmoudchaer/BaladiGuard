import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';

import { colors, radii, spacing, typography } from '@/theme';
import { formatStatusLabel } from '@/theme/labels';
import type { TicketStatus } from '@/types/ticket';

type StatusChipProps = {
  status: TicketStatus;
};

export function StatusChip({ status }: StatusChipProps) {
  const tone = colors.status[status] ?? colors.status.CLOSED;

  return (
    <View
      style={[styles.chip, { backgroundColor: tone.bg }]}
      accessibilityRole="text"
      accessibilityLabel={`Status ${formatStatusLabel(status)}`}
    >
      <View style={[styles.dot, { backgroundColor: tone.fg }]} />
      <Text style={[styles.label, { color: tone.fg }]}>{formatStatusLabel(status)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing[1],
    paddingHorizontal: spacing[2],
    paddingVertical: spacing[1],
    borderRadius: radii.sm,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: radii.pill,
  },
  label: {
    fontSize: typography.metadata,
    fontWeight: '700',
  },
});

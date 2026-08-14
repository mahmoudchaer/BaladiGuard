import { ScrollView, StyleSheet, View } from 'react-native';
import { Icon, Text } from 'react-native-paper';

import { TactilePressable } from '@/components/TactilePressable';
import { colors, radii, spacing, touchTargetMin, typography } from '@/theme';
import { formatCategoryLabel, formatStatusLabel } from '@/theme/labels';
import type { TicketStatus } from '@/types/ticket';
import type { PublicBrowseFilters } from '@/utils/publicMapClustering';

const STATUS_OPTIONS: Array<TicketStatus | 'ALL'> = [
  'ALL',
  'IN_PROGRESS',
  'UNDER_REVIEW',
  'ASSIGNED',
  'RESOLVED',
  'SUBMITTED',
  'CLOSED',
];

type PublicReportFiltersProps = {
  filters: PublicBrowseFilters;
  categories: string[];
  onChange: (next: PublicBrowseFilters) => void;
};

export function PublicReportFilters({ filters, categories, onChange }: PublicReportFiltersProps) {
  return (
    <View style={styles.wrap} testID="public-report-filters">
      <View style={styles.headingRow}>
        <View>
          <Text style={styles.heading}>Refine results</Text>
          <Text style={styles.hint}>Map and list update together</Text>
        </View>
        <Icon source="tune-variant" size={20} color={colors.textMuted} />
      </View>

      <Text style={styles.groupLabel}>STATUS</Text>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.row}
        accessibilityRole="tablist"
      >
        {STATUS_OPTIONS.map((status) => {
          const selected = filters.status === status;
          const label = status === 'ALL' ? 'All statuses' : formatStatusLabel(status);
          return (
            <TactilePressable
              key={status}
              onPress={() => onChange({ ...filters, status })}
              style={[styles.chip, selected && styles.chipSelected]}
              testID={`public-filter-status-${status}`}
              accessibilityRole="button"
              accessibilityState={{ selected }}
              accessibilityLabel={`Filter status ${label}`}
            >
              <Text style={[styles.chipLabel, selected && styles.chipLabelSelected]}>{label}</Text>
            </TactilePressable>
          );
        })}
      </ScrollView>

      <Text style={styles.groupLabel}>CATEGORY</Text>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.row}
        accessibilityRole="tablist"
      >
        <TactilePressable
          onPress={() => onChange({ ...filters, category: 'ALL' })}
          style={[styles.chip, filters.category === 'ALL' && styles.chipSelected]}
          testID="public-filter-category-ALL"
          accessibilityRole="button"
          accessibilityState={{ selected: filters.category === 'ALL' }}
          accessibilityLabel="Filter category All categories"
        >
          <Text style={[styles.chipLabel, filters.category === 'ALL' && styles.chipLabelSelected]}>
            All categories
          </Text>
        </TactilePressable>
        {categories.map((category) => {
          const selected = filters.category === category;
          return (
            <TactilePressable
              key={category}
              onPress={() => onChange({ ...filters, category })}
              style={[styles.chip, selected && styles.chipSelected]}
              testID={`public-filter-category-${category}`}
              accessibilityRole="button"
              accessibilityState={{ selected }}
              accessibilityLabel={`Filter category ${formatCategoryLabel(category)}`}
            >
              <Text style={[styles.chipLabel, selected && styles.chipLabelSelected]}>
                {formatCategoryLabel(category)}
              </Text>
            </TactilePressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    gap: spacing[3],
    paddingVertical: spacing[1],
  },
  headingRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  heading: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.text,
  },
  hint: {
    marginTop: 2,
    fontSize: 12,
    color: colors.textMuted,
  },
  groupLabel: {
    marginLeft: spacing[1],
    marginBottom: -spacing[1],
    fontSize: 10,
    fontWeight: '600',
    letterSpacing: 0.65,
    color: colors.textMuted,
  },
  row: {
    gap: spacing[2],
    paddingRight: spacing[5],
  },
  chip: {
    minHeight: touchTargetMin,
    paddingHorizontal: spacing[3],
    borderRadius: radii.pill,
    backgroundColor: colors.surface,
    justifyContent: 'center',
  },
  chipSelected: {
    backgroundColor: colors.brand,
  },
  chipLabel: {
    color: colors.textSecondary,
    fontSize: typography.metadata,
    fontWeight: '600',
  },
  chipLabelSelected: {
    color: colors.textInverse,
  },
});

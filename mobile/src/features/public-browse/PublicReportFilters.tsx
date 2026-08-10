import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';

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
      <Text variant="labelLarge" style={styles.heading}>
        Filter public map
      </Text>
      <Text variant="bodySmall" style={styles.hint}>
        Filters apply to both the map clusters and the list alternative.
      </Text>

      <Text variant="labelMedium" style={styles.groupLabel}>
        Status
      </Text>
      <View style={styles.row} accessibilityRole="tablist">
        {STATUS_OPTIONS.map((status) => {
          const selected = filters.status === status;
          const label = status === 'ALL' ? 'All statuses' : formatStatusLabel(status);
          return (
            <Pressable
              key={status}
              onPress={() => onChange({ ...filters, status })}
              style={[styles.chip, selected && styles.chipSelected]}
              testID={`public-filter-status-${status}`}
              accessibilityRole="button"
              accessibilityState={{ selected }}
              accessibilityLabel={`Filter status ${label}`}
            >
              <Text
                variant="labelMedium"
                style={[styles.chipLabel, selected && styles.chipLabelSelected]}
              >
                {label}
              </Text>
            </Pressable>
          );
        })}
      </View>

      <Text variant="labelMedium" style={styles.groupLabel}>
        Category
      </Text>
      <View style={styles.row} accessibilityRole="tablist">
        <Pressable
          onPress={() => onChange({ ...filters, category: 'ALL' })}
          style={[styles.chip, filters.category === 'ALL' && styles.chipSelected]}
          testID="public-filter-category-ALL"
          accessibilityRole="button"
          accessibilityState={{ selected: filters.category === 'ALL' }}
          accessibilityLabel="Filter category All categories"
        >
          <Text
            variant="labelMedium"
            style={[styles.chipLabel, filters.category === 'ALL' && styles.chipLabelSelected]}
          >
            All categories
          </Text>
        </Pressable>
        {categories.map((category) => {
          const selected = filters.category === category;
          return (
            <Pressable
              key={category}
              onPress={() => onChange({ ...filters, category })}
              style={[styles.chip, selected && styles.chipSelected]}
              testID={`public-filter-category-${category}`}
              accessibilityRole="button"
              accessibilityState={{ selected }}
              accessibilityLabel={`Filter category ${formatCategoryLabel(category)}`}
            >
              <Text
                variant="labelMedium"
                style={[styles.chipLabel, selected && styles.chipLabelSelected]}
              >
                {formatCategoryLabel(category)}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    gap: spacing[2],
  },
  heading: {
    fontWeight: '700',
    color: colors.text,
  },
  hint: {
    color: colors.textMuted,
  },
  groupLabel: {
    color: colors.textSecondary,
    marginTop: spacing[1],
  },
  row: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing[2],
  },
  chip: {
    minHeight: touchTargetMin,
    paddingHorizontal: spacing[3],
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    backgroundColor: colors.surface,
    justifyContent: 'center',
  },
  chipSelected: {
    backgroundColor: colors.brandSoft,
    borderColor: colors.brand,
  },
  chipLabel: {
    color: colors.textSecondary,
    fontSize: typography.metadata,
    fontWeight: '600',
  },
  chipLabelSelected: {
    color: colors.brandDark,
  },
});

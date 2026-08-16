import { ScrollView, StyleSheet, View } from 'react-native';
import { Icon, Text } from 'react-native-paper';

import { TactilePressable } from '@/components/TactilePressable';
import { useI18n } from '@/i18n/LocaleProvider';
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
  const { t } = useI18n();
  return (
    <View style={styles.wrap} testID="public-report-filters">
      <View style={styles.headingRow}>
        <View>
          <Text style={styles.heading}>{t('explore.refine')}</Text>
          <Text style={styles.hint}>{t('explore.refineHint')}</Text>
        </View>
        <Icon source="tune-variant" size={20} color={colors.textMuted} />
      </View>

      <Text style={styles.groupLabel}>{t('explore.status')}</Text>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.row}
        accessibilityRole="tablist"
      >
        {STATUS_OPTIONS.map((status) => {
          const selected = filters.status === status;
          const label = status === 'ALL' ? t('explore.allStatuses') : formatStatusLabel(status);
          return (
            <TactilePressable
              key={status}
              onPress={() => onChange({ ...filters, status })}
              style={[styles.chip, selected && styles.chipSelected]}
              testID={`public-filter-status-${status}`}
              accessibilityRole="button"
              accessibilityState={{ selected }}
              accessibilityLabel={t('explore.filterStatus', { label })}
            >
              <Text style={[styles.chipLabel, selected && styles.chipLabelSelected]}>{label}</Text>
            </TactilePressable>
          );
        })}
      </ScrollView>

      <Text style={styles.groupLabel}>{t('explore.category')}</Text>
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
          accessibilityLabel={t('explore.filterCategory', { label: t('explore.allCategories') })}
        >
          <Text style={[styles.chipLabel, filters.category === 'ALL' && styles.chipLabelSelected]}>
            {t('explore.allCategories')}
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
              accessibilityLabel={t('explore.filterCategory', {
                label: formatCategoryLabel(category),
              })}
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

import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';

import { CivicIllustration } from '@/components/CivicIllustration';
import { useI18n } from '@/i18n/LocaleProvider';
import { colors, radii, spacing, touchTargetMin } from '@/theme';
import type { PublicTicketResponse } from '@/types/ticket';
import { partitionPlottableReports } from '@/utils/publicMapClustering';

type PublicReportsMapProps = {
  reports: PublicTicketResponse[];
  onOpenReport: (ticketNumber: string) => void;
};

/**
 * Browser-safe companion to the native map. `react-native-maps` does not ship a
 * web implementation, so Expo resolves this file on web and keeps the native
 * MapView implementation for iOS and Android.
 */
export function PublicReportsMap({ reports, onOpenReport }: PublicReportsMapProps) {
  const { t } = useI18n();
  const { plottable } = partitionPlottableReports(reports);

  if (plottable.length === 0) {
    return (
      <View style={styles.emptyMap} testID="public-map-empty">
        <CivicIllustration name="lebanon-service-map" style={styles.artwork} />
        <Text variant="bodyMedium" style={styles.centeredText}>
          {t('explore.emptyMap')}
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.mapFallback} testID="public-reports-map">
      <CivicIllustration name="lebanon-service-map" style={styles.artwork} />
      <Text variant="bodySmall" style={styles.centeredText} testID="public-map-list-hint">
        {t('explore.mapHint')}
      </Text>
      <View style={styles.locationList}>
        {plottable.slice(0, 6).map(({ report }) => (
          <Pressable
            key={report.ticketNumber}
            accessibilityRole="button"
            accessibilityLabel={t('explore.publicReportA11y', {
              ticketNumber: report.ticketNumber,
            })}
            onPress={() => onOpenReport(report.ticketNumber)}
            style={({ pressed }) => [styles.locationButton, pressed && styles.pressed]}
            testID={`public-map-marker-${report.ticketNumber}`}
          >
            <Text style={styles.ticketNumber}>{report.ticketNumber}</Text>
            <Text style={styles.address} numberOfLines={1}>
              {report.location.addressText}
            </Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  mapFallback: {
    padding: spacing[4],
    borderRadius: radii.lg,
    backgroundColor: colors.surface,
    gap: spacing[3],
  },
  emptyMap: {
    padding: spacing[4],
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderStyle: 'dashed',
    backgroundColor: colors.surface,
    gap: spacing[2],
  },
  artwork: {
    width: 180,
    height: 130,
  },
  centeredText: {
    color: colors.textSecondary,
    textAlign: 'center',
  },
  locationList: {
    gap: spacing[2],
  },
  locationButton: {
    minHeight: touchTargetMin,
    paddingHorizontal: spacing[3],
    paddingVertical: spacing[2],
    borderRadius: radii.sm,
    backgroundColor: colors.surfaceSubtle,
  },
  pressed: {
    backgroundColor: colors.brandSoft,
  },
  ticketNumber: {
    color: colors.brandDark,
    fontWeight: '700',
  },
  address: {
    color: colors.textMuted,
    fontSize: 12,
  },
});

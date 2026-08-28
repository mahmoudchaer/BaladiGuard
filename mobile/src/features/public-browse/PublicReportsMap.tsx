import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
  Text as RNText,
} from 'react-native';
import type MapView from 'react-native-maps';
import type { Region } from 'react-native-maps';
import { Button, Text } from 'react-native-paper';

import { useI18n } from '@/i18n/LocaleProvider';
import { StatusChip } from '@/components/StatusChip';
import { colors, radii, spacing, touchTargetMin, typography } from '@/theme';
import { formatCategoryLabel } from '@/theme/labels';
import type { PublicTicketResponse } from '@/types/ticket';
import {
  clusterCanExpandByZoom,
  clusterPublicReports,
  initialRegionForPlottable,
  partitionPlottableReports,
  regionForReports,
  type PublicMapRegion,
} from '@/utils/publicMapClustering';

const testNativeMaps =
  process.env.NODE_ENV === 'test'
    ? ({ default: 'MapView', Marker: 'Marker' } as unknown as typeof import('react-native-maps'))
    : null;
const nativeMaps =
  testNativeMaps ??
  (Platform.OS === 'web'
    ? null
    : (require('react-native-maps') as typeof import('react-native-maps')));
const NativeMapView = nativeMaps?.default;
const NativeMarker = nativeMaps?.Marker;

type PublicReportsMapProps = {
  reports: PublicTicketResponse[];
  onOpenReport: (ticketNumber: string) => void;
};

export function PublicReportsMap({ reports, onOpenReport }: PublicReportsMapProps) {
  const { t } = useI18n();
  const mapRef = useRef<MapView | null>(null);
  const { plottable } = useMemo(() => partitionPlottableReports(reports), [reports]);
  const plottableKey = plottable.map((p) => p.ticketNumber).join('|');

  const [region, setRegion] = useState<PublicMapRegion>(() => initialRegionForPlottable(plottable));
  const [clusterPicker, setClusterPicker] = useState<PublicTicketResponse[] | null>(null);

  useEffect(() => {
    const next = initialRegionForPlottable(plottable);
    setRegion(next);
    mapRef.current?.animateToRegion(next, 200);
    setClusterPicker(null);
  }, [plottableKey]); // eslint-disable-line react-hooks/exhaustive-deps -- key tracks membership

  const features = useMemo(() => clusterPublicReports(plottable, region), [plottable, region]);

  const handleRegionChangeComplete = useCallback((next: Region) => {
    setRegion({
      latitude: next.latitude,
      longitude: next.longitude,
      latitudeDelta: next.latitudeDelta,
      longitudeDelta: next.longitudeDelta,
    });
  }, []);

  const openClusterPicker = useCallback((clusterReports: PublicTicketResponse[]) => {
    const sorted = [...clusterReports].sort((a, b) => a.ticketNumber.localeCompare(b.ticketNumber));
    setClusterPicker(sorted);
  }, []);

  const expandCluster = useCallback(
    (clusterReports: PublicTicketResponse[]) => {
      const points = partitionPlottableReports(clusterReports).plottable;
      if (points.length === 0) {
        return;
      }
      if (points.length === 1) {
        onOpenReport(points[0].ticketNumber);
        return;
      }
      // Identical / sub-cell coordinates never expand into singles on zoom.
      if (!clusterCanExpandByZoom(points)) {
        openClusterPicker(points.map((point) => point.report));
        return;
      }
      const next = regionForReports(points, 1.35);
      setRegion(next);
      mapRef.current?.animateToRegion(next, 280);
    },
    [onOpenReport, openClusterPicker],
  );

  const closeClusterPicker = useCallback(() => {
    setClusterPicker(null);
  }, []);

  const pickReport = useCallback(
    (ticketNumber: string) => {
      setClusterPicker(null);
      onOpenReport(ticketNumber);
    },
    [onOpenReport],
  );

  if (plottable.length === 0) {
    return (
      <View style={styles.emptyMap} testID="public-map-empty">
        <Text variant="bodyMedium" style={styles.emptyMapText}>
          {t('explore.emptyMap')}
        </Text>
      </View>
    );
  }

  if (!NativeMapView || !NativeMarker) {
    return (
      <View style={styles.webMapFallback} testID="public-reports-map">
        <Text variant="bodySmall" style={styles.webMapHint} testID="public-map-list-hint">
          {t('explore.mapHint')}
        </Text>
        {plottable.slice(0, 6).map(({ report }) => (
          <Pressable
            key={report.ticketNumber}
            accessibilityRole="button"
            accessibilityLabel={t('explore.publicReportA11y', {
              ticketNumber: report.ticketNumber,
            })}
            onPress={() => onOpenReport(report.ticketNumber)}
            style={styles.webLocationButton}
            testID={`public-map-marker-${report.ticketNumber}`}
          >
            <Text style={styles.webTicketNumber}>{report.ticketNumber}</Text>
            <Text style={styles.webAddress} numberOfLines={1}>
              {report.location.addressText}
            </Text>
          </Pressable>
        ))}
      </View>
    );
  }

  return (
    <View style={styles.mapWrap} testID="public-reports-map">
      <NativeMapView
        ref={mapRef}
        style={styles.map}
        initialRegion={region}
        onRegionChangeComplete={handleRegionChangeComplete}
        testID="public-map-view"
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
      >
        {features.map((feature) => {
          if (feature.kind === 'single') {
            return (
              <NativeMarker
                key={feature.id}
                coordinate={{
                  latitude: feature.latitude,
                  longitude: feature.longitude,
                }}
                title={feature.report.ticketNumber}
                description={feature.report.location.addressText}
                pinColor={colors.status[feature.report.status]?.fg ?? colors.brand}
                onPress={() => onOpenReport(feature.report.ticketNumber)}
                testID={`public-map-marker-${feature.report.ticketNumber}`}
                accessibilityLabel={t('explore.publicReportA11y', {
                  ticketNumber: feature.report.ticketNumber,
                })}
              />
            );
          }

          const points = partitionPlottableReports(feature.reports).plottable;
          const mayExpand = clusterCanExpandByZoom(points);
          return (
            <NativeMarker
              key={feature.id}
              coordinate={{
                latitude: feature.latitude,
                longitude: feature.longitude,
              }}
              onPress={() => expandCluster(feature.reports)}
              testID={`public-map-cluster-${feature.id}`}
              accessibilityLabel={
                mayExpand
                  ? t('explore.clusterZoomA11y', { count: feature.count })
                  : t('explore.clusterPickA11y', { count: feature.count })
              }
              tracksViewChanges={false}
            >
              <View
                style={styles.clusterBubble}
                testID={`public-map-cluster-count-${feature.count}`}
              >
                <RNText style={styles.clusterCount}>{feature.count}</RNText>
              </View>
            </NativeMarker>
          );
        })}
      </NativeMapView>
      <Text variant="bodySmall" style={styles.mapHint} testID="public-map-list-hint">
        {t('explore.mapHint')}
      </Text>

      <Modal
        visible={clusterPicker !== null}
        transparent
        animationType="fade"
        onRequestClose={closeClusterPicker}
        testID="public-map-cluster-picker"
      >
        <View style={styles.pickerBackdrop}>
          <View style={styles.pickerSheet} accessibilityViewIsModal>
            <Text variant="titleMedium" style={styles.pickerTitle}>
              {t('explore.clusterTitle')}
            </Text>
            <Text variant="bodySmall" style={styles.pickerSubtitle}>
              {t('explore.clusterSubtitle')}
            </Text>
            <ScrollView
              style={styles.pickerList}
              contentContainerStyle={styles.pickerListContent}
              testID="public-map-cluster-picker-list"
            >
              {(clusterPicker ?? []).map((report) => (
                <Pressable
                  key={report.ticketNumber}
                  style={styles.pickerRow}
                  onPress={() => pickReport(report.ticketNumber)}
                  testID={`public-map-cluster-pick-${report.ticketNumber}`}
                  accessibilityRole="button"
                  accessibilityLabel={t('explore.openReport', {
                    ticketNumber: report.ticketNumber,
                  })}
                >
                  <View style={styles.pickerRowTop}>
                    <Text variant="titleSmall" style={styles.pickerTicket}>
                      {report.ticketNumber}
                    </Text>
                    <StatusChip status={report.status} />
                  </View>
                  <Text variant="bodySmall" style={styles.pickerMeta} numberOfLines={2}>
                    {formatCategoryLabel(report.category)} ·{' '}
                    {report.location.addressText ||
                      report.mapLocation?.addressText ||
                      t('report.location')}
                  </Text>
                </Pressable>
              ))}
            </ScrollView>
            <Button
              mode="outlined"
              onPress={closeClusterPicker}
              testID="public-map-cluster-picker-close"
              accessibilityLabel={t('explore.closeLocationList')}
            >
              {t('common.close')}
            </Button>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  mapWrap: {
    // Keep geographic orientation LTR even when the app chrome is RTL (#259).
    direction: 'ltr',
    borderRadius: radii.lg,
    overflow: 'hidden',
    backgroundColor: colors.surface,
    gap: spacing[2],
  },
  map: {
    height: 260,
  },
  mapHint: {
    color: colors.textMuted,
    paddingHorizontal: spacing[4],
    paddingBottom: spacing[3],
    lineHeight: 17,
  },
  emptyMap: {
    padding: spacing[4],
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderStyle: 'dashed',
    backgroundColor: colors.surface,
  },
  emptyMapText: {
    color: colors.textSecondary,
  },
  webMapFallback: {
    padding: spacing[4],
    borderRadius: radii.lg,
    backgroundColor: colors.surface,
    gap: spacing[2],
  },
  webMapHint: {
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing[1],
  },
  webLocationButton: {
    minHeight: touchTargetMin,
    padding: spacing[3],
    borderRadius: radii.sm,
    backgroundColor: colors.surfaceSubtle,
  },
  webTicketNumber: {
    color: colors.brandDark,
    fontWeight: '700',
  },
  webAddress: {
    color: colors.textMuted,
    fontSize: 12,
  },
  clusterBubble: {
    minWidth: 36,
    minHeight: 36,
    borderRadius: 18,
    backgroundColor: colors.brand,
    borderWidth: 2,
    borderColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing[2],
  },
  clusterCount: {
    color: colors.textInverse,
    fontWeight: '700',
    fontSize: typography.label,
  },
  pickerBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(26, 35, 50, 0.45)',
    justifyContent: 'center',
    padding: spacing[4],
  },
  pickerSheet: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    padding: spacing[4],
    maxHeight: '70%',
    gap: spacing[3],
  },
  pickerTitle: {
    color: colors.brandDark,
    fontWeight: '700',
  },
  pickerSubtitle: {
    color: colors.textSecondary,
  },
  pickerList: {
    maxHeight: 280,
  },
  pickerListContent: {
    gap: spacing[2],
    paddingBottom: spacing[1],
  },
  pickerRow: {
    minHeight: touchTargetMin,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    padding: spacing[3],
    backgroundColor: colors.surfaceSubtle,
    gap: spacing[1],
  },
  pickerRowTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing[2],
  },
  pickerTicket: {
    color: colors.text,
    fontWeight: '700',
    flexShrink: 1,
  },
  pickerMeta: {
    color: colors.textMuted,
  },
});

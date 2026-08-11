import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, View, Text as RNText } from 'react-native';
import MapView, { Marker, type Region } from 'react-native-maps';
import { Button, Text } from 'react-native-paper';

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

type PublicReportsMapProps = {
  reports: PublicTicketResponse[];
  onOpenReport: (ticketNumber: string) => void;
};

export function PublicReportsMap({ reports, onOpenReport }: PublicReportsMapProps) {
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
          No mappable locations in the current public results. Use the list below.
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.mapWrap} testID="public-reports-map">
      <MapView
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
              <Marker
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
                accessibilityLabel={`Public report ${feature.report.ticketNumber}`}
              />
            );
          }

          const points = partitionPlottableReports(feature.reports).plottable;
          const mayExpand = clusterCanExpandByZoom(points);
          return (
            <Marker
              key={feature.id}
              coordinate={{
                latitude: feature.latitude,
                longitude: feature.longitude,
              }}
              onPress={() => expandCluster(feature.reports)}
              testID={`public-map-cluster-${feature.id}`}
              accessibilityLabel={
                mayExpand
                  ? `Cluster of ${feature.count} public reports. Activate to zoom in.`
                  : `Cluster of ${feature.count} public reports at the same location. Activate to choose a report.`
              }
              tracksViewChanges={false}
            >
              <View
                style={styles.clusterBubble}
                testID={`public-map-cluster-count-${feature.count}`}
              >
                <RNText style={styles.clusterCount}>{feature.count}</RNText>
              </View>
            </Marker>
          );
        })}
      </MapView>
      <Text variant="bodySmall" style={styles.mapHint} testID="public-map-list-hint">
        Prefer the report list below if the map is hard to use. Clusters show only public reports.
        Same-location clusters open a short list so you can still choose a report.
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
              Reports at this location
            </Text>
            <Text variant="bodySmall" style={styles.pickerSubtitle}>
              These public reports share the same map pin. Choose one to open.
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
                  accessibilityLabel={`Open public report ${report.ticketNumber}`}
                >
                  <View style={styles.pickerRowTop}>
                    <Text variant="titleSmall" style={styles.pickerTicket}>
                      {report.ticketNumber}
                    </Text>
                    <StatusChip status={report.status} />
                  </View>
                  <Text variant="bodySmall" style={styles.pickerMeta} numberOfLines={2}>
                    {formatCategoryLabel(report.category)} ·{' '}
                    {report.location.addressText || report.mapLocation?.addressText || 'Location'}
                  </Text>
                </Pressable>
              ))}
            </ScrollView>
            <Button
              mode="outlined"
              onPress={closeClusterPicker}
              testID="public-map-cluster-picker-close"
              accessibilityLabel="Close location report list"
            >
              Close
            </Button>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  mapWrap: {
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
    backgroundColor: colors.surface,
    gap: spacing[2],
  },
  map: {
    height: 220,
  },
  mapHint: {
    color: colors.textMuted,
    paddingHorizontal: spacing[3],
    paddingBottom: spacing[2],
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

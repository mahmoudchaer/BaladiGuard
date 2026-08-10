import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { StyleSheet, View, Text as RNText } from 'react-native';
import MapView, { Marker, type Region } from 'react-native-maps';
import { Text } from 'react-native-paper';

import { colors, radii, spacing, typography } from '@/theme';
import type { PublicTicketResponse } from '@/types/ticket';
import {
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

  useEffect(() => {
    const next = initialRegionForPlottable(plottable);
    setRegion(next);
    mapRef.current?.animateToRegion(next, 200);
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
      const next = regionForReports(points, 1.35);
      setRegion(next);
      mapRef.current?.animateToRegion(next, 280);
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

          return (
            <Marker
              key={feature.id}
              coordinate={{
                latitude: feature.latitude,
                longitude: feature.longitude,
              }}
              onPress={() => expandCluster(feature.reports)}
              testID={`public-map-cluster-${feature.id}`}
              accessibilityLabel={`Cluster of ${feature.count} public reports. Activate to zoom in.`}
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
      </Text>
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
});

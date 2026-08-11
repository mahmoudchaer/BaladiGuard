import { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import MapView, { Marker } from 'react-native-maps';
import { ActivityIndicator, Banner, Button, Text } from 'react-native-paper';
import { useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ReportPhoto } from '@/components/ReportPhoto';
import { StatusChip } from '@/components/StatusChip';
import { getPublicTicketByNumber } from '@/services/api/tickets';
import { colors, radii, spacing, typography } from '@/theme';
import { formatCategoryLabel } from '@/theme/labels';
import type { PublicTicketResponse } from '@/types/ticket';
import { openInMapsApp } from '@/utils/openMaps';
import { isValidMapCoordinate } from '@/utils/publicMapClustering';

export default function PublicReportDetailScreen() {
  const { ticketNumber } = useLocalSearchParams<{ ticketNumber?: string | string[] }>();
  const selectedTicketNumber = Array.isArray(ticketNumber) ? ticketNumber[0] : ticketNumber;
  const [report, setReport] = useState<PublicTicketResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadReport() {
      if (!selectedTicketNumber) {
        setError('Unable to open that public report.');
        setIsLoading(false);
        return;
      }
      setIsLoading(true);
      setError(null);
      try {
        const response = await getPublicTicketByNumber(selectedTicketNumber);
        if (active) {
          setReport(response);
        }
      } catch (loadError) {
        if (active) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : 'Unable to load that public report right now.',
          );
        }
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    }

    void loadReport();
    return () => {
      active = false;
    };
  }, [selectedTicketNumber]);

  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.container}>
        {isLoading ? (
          <View style={styles.loading} testID="public-report-detail-loading">
            <ActivityIndicator color={colors.brand} />
            <Text variant="bodyMedium" style={styles.loadingText}>
              Loading public report...
            </Text>
          </View>
        ) : null}

        {error ? (
          <Banner visible icon="alert-circle" style={styles.errorBanner}>
            {error}
          </Banner>
        ) : null}

        {report ? (
          <View style={styles.content} testID="public-report-detail">
            <View style={styles.header}>
              <Text variant="headlineSmall" style={styles.ticketNumber}>
                {report.ticketNumber}
              </Text>
              <StatusChip status={report.status} />
            </View>

            <ReportPhoto
              uri={report.photoUrl}
              accessibilityLabel={`Photo for report ${report.ticketNumber}`}
              testID="public-report-detail-photo"
              variant="hero"
            />

            <View style={styles.mapWrap}>
              <MapView
                style={styles.map}
                initialRegion={{
                  latitude: report.mapLocation.latitude,
                  longitude: report.mapLocation.longitude,
                  latitudeDelta: 0.025,
                  longitudeDelta: 0.025,
                }}
              >
                <Marker
                  coordinate={{
                    latitude: report.mapLocation.latitude,
                    longitude: report.mapLocation.longitude,
                  }}
                  title={report.ticketNumber}
                  description={report.mapLocation.addressText}
                  pinColor={colors.status[report.status]?.fg ?? colors.brand}
                />
              </MapView>
              <Button
                mode="contained"
                icon="map-marker-outline"
                style={styles.mapsButton}
                contentStyle={styles.mapsButtonContent}
                buttonColor={colors.brand}
                textColor={colors.textInverse}
                disabled={
                  !isValidMapCoordinate(report.mapLocation?.latitude, report.mapLocation?.longitude)
                }
                onPress={() => {
                  const latitude = report.mapLocation?.latitude;
                  const longitude = report.mapLocation?.longitude;
                  if (!isValidMapCoordinate(latitude, longitude)) {
                    return;
                  }
                  void openInMapsApp({
                    latitude,
                    longitude,
                    label: report.mapLocation.addressText || report.ticketNumber,
                  });
                }}
                testID="public-report-detail-maps"
                accessibilityLabel="Open this report location in maps"
              >
                Open in Maps
              </Button>
            </View>

            <View style={styles.card}>
              <Text variant="titleMedium" style={styles.cardTitle}>
                Summary
              </Text>
              <Text variant="bodyMedium" style={styles.description}>
                {report.description}
              </Text>
              <Text variant="bodySmall" style={styles.metaText}>
                {formatCategoryLabel(report.category)} · {report.location.addressText}
              </Text>
              {report.department ? (
                <Text variant="bodySmall" style={styles.metaText}>
                  Assigned to {report.department.name}
                </Text>
              ) : null}
              <Text variant="bodySmall" style={styles.metaText}>
                Reported by {report.attribution.displayName}
              </Text>
            </View>
          </View>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background,
  },
  container: {
    padding: spacing[5],
    gap: spacing[4],
    paddingBottom: spacing[8],
  },
  loading: {
    minHeight: 160,
    justifyContent: 'center',
    alignItems: 'center',
    gap: spacing[2],
  },
  loadingText: {
    color: colors.textSecondary,
  },
  errorBanner: {
    borderRadius: radii.md,
    backgroundColor: colors.dangerSoft,
  },
  content: {
    gap: spacing[4],
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: spacing[3],
  },
  ticketNumber: {
    color: colors.brandDark,
    fontWeight: '700',
    flexShrink: 1,
  },
  mapWrap: {
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
    backgroundColor: colors.surface,
    gap: spacing[3],
    paddingBottom: spacing[3],
  },
  map: {
    height: 220,
  },
  mapsButton: {
    marginHorizontal: spacing[3],
    borderRadius: radii.md,
  },
  mapsButtonContent: {
    minHeight: 44,
  },
  card: {
    gap: spacing[2],
    padding: spacing[4],
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  cardTitle: {
    fontWeight: '700',
    color: colors.text,
  },
  description: {
    color: colors.text,
    lineHeight: 21,
  },
  metaText: {
    color: colors.textMuted,
    fontSize: typography.metadata,
  },
});

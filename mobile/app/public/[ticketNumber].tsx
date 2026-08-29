import { useCallback, useEffect, useRef, useState } from 'react';
import { Platform, ScrollView, StyleSheet, View } from 'react-native';
import { ActivityIndicator, Banner, Button, Text } from 'react-native-paper';
import { useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ReportPhoto } from '@/components/ReportPhoto';
import { StatusChip } from '@/components/StatusChip';
import { useI18n } from '@/i18n/LocaleProvider';
import { getPublicTicketByNumber } from '@/services/api/tickets';
import { colors, radii, spacing, typography } from '@/theme';
import { formatCategoryLabel } from '@/theme/labels';
import type { PublicTicketResponse } from '@/types/ticket';
import { openInMapsApp } from '@/utils/openMaps';
import { isValidMapCoordinate } from '@/utils/publicMapClustering';

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

export default function PublicReportDetailScreen() {
  const { t } = useI18n();
  const { ticketNumber } = useLocalSearchParams<{ ticketNumber?: string | string[] }>();
  const selectedTicketNumber = Array.isArray(ticketNumber) ? ticketNumber[0] : ticketNumber;
  const [report, setReport] = useState<PublicTicketResponse | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(selectedTicketNumber));
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [usedLoadFallback, setUsedLoadFallback] = useState(false);
  const requestGeneration = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  const loadReport = useCallback(() => {
    if (!selectedTicketNumber) {
      setIsLoading(false);
      return;
    }
    const generation = requestGeneration.current + 1;
    requestGeneration.current = generation;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setIsLoading(true);
    setErrorMessage(null);
    setUsedLoadFallback(false);
    setReport(null);
    void getPublicTicketByNumber(selectedTicketNumber, { signal: controller.signal })
      .then((response) => {
        if (generation === requestGeneration.current) setReport(response);
      })
      .catch((loadError: unknown) => {
        if (generation !== requestGeneration.current) return;
        if (loadError instanceof Error && loadError.name === 'AbortError') return;
        if (loadError instanceof Error) {
          setErrorMessage(loadError.message);
        } else {
          setUsedLoadFallback(true);
        }
      })
      .finally(() => {
        if (generation === requestGeneration.current) setIsLoading(false);
      });
    return () => {
      controller.abort();
    };
  }, [selectedTicketNumber]);

  useEffect(() => loadReport(), [loadReport]);

  const error = !selectedTicketNumber
    ? t('public.unableOpen')
    : (errorMessage ?? (usedLoadFallback ? t('public.unableLoad') : null));

  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.container}>
        {isLoading ? (
          <View style={styles.loading} testID="public-report-detail-loading">
            <ActivityIndicator color={colors.brand} />
            <Text variant="bodyMedium" style={styles.loadingText}>
              {t('public.loading')}
            </Text>
          </View>
        ) : null}

        {error ? (
          <>
            <Banner
              visible
              icon="alert-circle"
              style={styles.errorBanner}
              testID="public-report-detail-error"
            >
              {error}
            </Banner>
            <Button
              mode="outlined"
              onPress={() => loadReport()}
              textColor={colors.brandDark}
              testID="public-report-detail-retry"
            >
              {t('common.tryAgain')}
            </Button>
          </>
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
              accessibilityLabel={t('public.photoAlt', { ticketNumber: report.ticketNumber })}
              testID="public-report-detail-photo"
              variant="hero"
            />

            <View style={styles.mapWrap}>
              {NativeMapView && NativeMarker ? (
                <NativeMapView
                  style={styles.map}
                  initialRegion={{
                    latitude: report.mapLocation.latitude,
                    longitude: report.mapLocation.longitude,
                    latitudeDelta: 0.025,
                    longitudeDelta: 0.025,
                  }}
                >
                  <NativeMarker
                    coordinate={{
                      latitude: report.mapLocation.latitude,
                      longitude: report.mapLocation.longitude,
                    }}
                    title={report.ticketNumber}
                    description={report.mapLocation.addressText}
                    pinColor={colors.status[report.status]?.fg ?? colors.brand}
                  />
                </NativeMapView>
              ) : (
                <View style={styles.webMapFallback}>
                  <Text variant="titleSmall" style={styles.webMapTitle}>
                    {report.mapLocation.addressText || report.location.addressText}
                  </Text>
                  <Text variant="bodySmall" style={styles.metaText}>
                    {report.mapLocation.latitude.toFixed(5)},{' '}
                    {report.mapLocation.longitude.toFixed(5)}
                  </Text>
                </View>
              )}
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
                accessibilityLabel={t('public.openMapsA11y')}
              >
                {t('public.openMaps')}
              </Button>
            </View>

            <View style={styles.card}>
              <Text variant="titleMedium" style={styles.cardTitle}>
                {t('public.summary')}
              </Text>
              <Text variant="bodyMedium" style={styles.description}>
                {report.description}
              </Text>
              <Text variant="bodySmall" style={styles.metaText}>
                {formatCategoryLabel(report.category)} · {report.location.addressText}
              </Text>
              {report.department ? (
                <Text variant="bodySmall" style={styles.metaText}>
                  {t('public.assignedTo', { name: report.department.name })}
                </Text>
              ) : null}
              <Text variant="bodySmall" style={styles.metaText}>
                {t('public.reportedBy', { name: report.attribution.displayName })}
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
    writingDirection: 'ltr',
  },
  mapWrap: {
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
    backgroundColor: colors.surface,
    gap: spacing[3],
    paddingBottom: spacing[3],
    direction: 'ltr',
  },
  map: {
    height: 220,
  },
  webMapFallback: {
    minHeight: 150,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing[4],
    gap: spacing[2],
    backgroundColor: colors.brandSoft,
  },
  webMapTitle: {
    color: colors.brandDark,
    textAlign: 'center',
    fontWeight: '700',
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

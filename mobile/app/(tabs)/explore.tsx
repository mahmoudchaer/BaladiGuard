import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { Banner, Button, Text } from 'react-native-paper';
import { useRouter, type Href } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useCitizenAuth } from '@/auth';
import { BrandMark } from '@/components/BrandMark';
import { ReportPhoto } from '@/components/ReportPhoto';
import { StatusChip } from '@/components/StatusChip';
import { PublicReportFilters } from '@/features/public-browse/PublicReportFilters';
import { PublicReportsMap } from '@/features/public-browse/PublicReportsMap';
import { getPublicTickets } from '@/services/api/tickets';
import { colors, radii, spacing, touchTargetMin } from '@/theme';
import { formatCategoryLabel } from '@/theme/labels';
import type { PublicTicketResponse } from '@/types/ticket';
import { openInMapsApp } from '@/utils/openMaps';
import {
  filterPublicReports,
  isValidMapCoordinate,
  partitionPlottableReports,
  uniquePublicCategories,
  type PublicBrowseFilters,
} from '@/utils/publicMapClustering';

const PUBLIC_FEED_LIMIT = 50;
const DEFAULT_FILTERS: PublicBrowseFilters = { status: 'ALL', category: 'ALL' };

export default function ExploreScreen() {
  const router = useRouter();
  const { isAuthenticated } = useCitizenAuth();
  const [reports, setReports] = useState<PublicTicketResponse[]>([]);
  const [filters, setFilters] = useState<PublicBrowseFilters>(DEFAULT_FILTERS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const loadSeqRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const seq = ++loadSeqRef.current;
    setLoading(true);
    setError(null);
    try {
      const response = await getPublicTickets({
        limit: PUBLIC_FEED_LIMIT,
        signal: controller.signal,
      });
      if (seq === loadSeqRef.current) setReports(response.items);
    } catch (cause) {
      if (seq === loadSeqRef.current && !controller.signal.aborted) {
        setError(cause instanceof Error ? cause.message : 'Unable to load community reports.');
      }
    } finally {
      if (seq === loadSeqRef.current) setLoading(false);
    }
  }, []);
  useEffect(() => {
    void load();
    return () => {
      loadSeqRef.current += 1;
      abortRef.current?.abort();
    };
  }, [load]);

  const filteredReports = useMemo(() => filterPublicReports(reports, filters), [reports, filters]);
  const categories = useMemo(() => uniquePublicCategories(reports), [reports]);
  const { skippedCount } = useMemo(
    () => partitionPlottableReports(filteredReports),
    [filteredReports],
  );

  const openPublicReport = (ticketNumber: string) =>
    router.push({
      pathname: '/public/[ticketNumber]',
      params: { ticketNumber },
    } as unknown as Href);

  return (
    <SafeAreaView style={styles.safeArea} edges={['top', 'left', 'right']}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.header}>
          <View style={styles.titleRow}>
            <BrandMark size={30} />
            <Text style={styles.title} accessibilityRole="header">
              Explore
            </Text>
          </View>
          <Text style={styles.subtitle}>
            Privacy-safe community reports published with coarse locations and approved photos.
          </Text>
        </View>
        {!isAuthenticated ? (
          <View style={styles.guestBar}>
            <Button mode="text" icon="arrow-left" onPress={() => router.replace('/' as Href)}>
              Welcome
            </Button>
            <Button
              mode="outlined"
              icon="barcode-scan"
              onPress={() => router.push('/track' as Href)}
            >
              Track with a code
            </Button>
          </View>
        ) : null}
        {error ? (
          <View style={styles.error}>
            <Banner visible icon="wifi-alert">
              {error}
            </Banner>
            <Button mode="outlined" onPress={() => void load()}>
              Try again
            </Button>
          </View>
        ) : null}
        {loading ? (
          <View style={styles.loading} testID="public-reports-loading">
            <ActivityIndicator color={colors.brand} />
            <Text style={styles.muted}>Loading community reports…</Text>
          </View>
        ) : null}
        {!loading && !error && reports.length === 0 ? (
          <View style={styles.empty} testID="explore-empty">
            <Text style={styles.emptyTitle}>No published reports yet</Text>
            <Text style={styles.muted}>Public reports will appear here after privacy review.</Text>
          </View>
        ) : null}
        {!loading && !error && reports.length > 0 ? (
          <View style={styles.publicContent}>
            <PublicReportFilters filters={filters} categories={categories} onChange={setFilters} />
            {filteredReports.length === 0 ? (
              <View style={styles.empty} testID="public-filter-empty">
                <Text style={styles.emptyTitle}>No reports match these filters</Text>
                <Text style={styles.muted}>Clear the filters to see the public map and list.</Text>
                <Button mode="outlined" onPress={() => setFilters(DEFAULT_FILTERS)}>
                  Clear filters
                </Button>
              </View>
            ) : (
              <>
                <PublicReportsMap reports={filteredReports} onOpenReport={openPublicReport} />
                {skippedCount > 0 ? (
                  <Text style={styles.mapNote} testID="public-map-skipped-count">
                    {skippedCount} public {skippedCount === 1 ? 'report has' : 'reports have'} no
                    usable map point and {skippedCount === 1 ? 'is' : 'are'} still listed below.
                  </Text>
                ) : null}
              </>
            )}
          </View>
        ) : null}
        <View style={styles.list} testID="public-report-feed">
          {filteredReports.map((report) => (
            <Pressable
              key={report.ticketNumber}
              testID={`public-report-card-${report.ticketNumber}`}
              accessibilityRole="button"
              accessibilityLabel={`Open public report ${report.ticketNumber}`}
              onPress={() => openPublicReport(report.ticketNumber)}
              style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}
            >
              <ReportPhoto
                uri={report.photoUrl}
                accessibilityLabel={`Approved public photo for ${report.ticketNumber}`}
                variant="compact"
              />
              <View style={styles.cardBody}>
                <View style={styles.cardTop}>
                  <Text style={styles.category} numberOfLines={1}>
                    {formatCategoryLabel(report.category)}
                  </Text>
                  <StatusChip status={report.status} />
                </View>
                <Text style={styles.description} numberOfLines={2}>
                  {report.description}
                </Text>
                <Text style={styles.meta} numberOfLines={1}>
                  {report.location.addressText}
                </Text>
                {isValidMapCoordinate(report.mapLocation.latitude, report.mapLocation.longitude) ? (
                  <Button
                    mode="text"
                    compact
                    icon="map-marker-outline"
                    onPress={(event) => {
                      event.stopPropagation();
                      void openInMapsApp({
                        latitude: report.mapLocation.latitude,
                        longitude: report.mapLocation.longitude,
                        label: report.mapLocation.addressText || report.location.addressText,
                      });
                    }}
                    testID={`public-report-directions-${report.ticketNumber}`}
                  >
                    Open coarse location
                  </Button>
                ) : null}
                <Text
                  style={styles.attribution}
                  testID={`public-report-attribution-${report.ticketNumber}`}
                >
                  Shared by {report.attribution.displayName}
                </Text>
              </View>
            </Pressable>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.background },
  scroll: { padding: spacing[5], paddingBottom: spacing[8], gap: spacing[5] },
  header: { gap: spacing[2] },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing[3] },
  title: { fontSize: 28, fontWeight: '800', color: colors.text },
  subtitle: { fontSize: 15, lineHeight: 22, color: colors.textSecondary },
  guestBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  error: { gap: spacing[3] },
  loading: { alignItems: 'center', paddingVertical: spacing[8], gap: spacing[3] },
  muted: { color: colors.textSecondary, textAlign: 'center' },
  empty: {
    padding: spacing[6],
    alignItems: 'center',
    gap: spacing[2],
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
  },
  emptyTitle: { fontSize: 17, fontWeight: '700', color: colors.text },
  publicContent: { gap: spacing[4] },
  mapNote: { fontSize: 12, lineHeight: 18, color: colors.textMuted },
  list: { gap: spacing[3] },
  card: {
    minHeight: touchTargetMin,
    flexDirection: 'row',
    padding: spacing[3],
    gap: spacing[3],
    borderRadius: radii.lg,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  cardPressed: { backgroundColor: colors.brandSoft, borderColor: colors.brand },
  cardBody: { flex: 1, gap: spacing[1] },
  cardTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing[2],
  },
  category: { flex: 1, fontWeight: '700', color: colors.text },
  description: { lineHeight: 20, color: colors.text },
  meta: { fontSize: 12, color: colors.textSecondary },
  attribution: { fontSize: 12, color: colors.textMuted },
});

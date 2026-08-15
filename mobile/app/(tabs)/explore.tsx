import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { Banner, Button, Text } from 'react-native-paper';
import { useRouter, type Href } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useCitizenAuth } from '@/auth';
import { useI18n } from '@/i18n/LocaleProvider';
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
  const { t } = useI18n();
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
        setError(cause instanceof Error ? cause.message : t('explore.loadFailed'));
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
          <Text style={styles.overline}>{t('explore.eyebrow')}</Text>
          <Text style={styles.title} accessibilityRole="header">
            {t('explore.title')}
          </Text>
          <Text style={styles.subtitle}>{t('explore.subtitle')}</Text>
        </View>
        {!isAuthenticated ? (
          <View style={styles.guestBar}>
            <Button mode="text" icon="arrow-left" onPress={() => router.replace('/' as Href)}>
              {t('explore.welcome')}
            </Button>
            <Button
              mode="outlined"
              icon="barcode-scan"
              onPress={() => router.push('/track' as Href)}
            >
              {t('explore.trackCode')}
            </Button>
          </View>
        ) : null}
        {error ? (
          <View style={styles.error}>
            <Banner visible icon="wifi-alert">
              {error}
            </Banner>
            <Button mode="outlined" onPress={() => void load()}>
              {t('common.tryAgain')}
            </Button>
          </View>
        ) : null}
        {loading ? (
          <View style={styles.loading} testID="public-reports-loading">
            <ActivityIndicator color={colors.brand} />
            <Text style={styles.muted}>{t('explore.loading')}</Text>
          </View>
        ) : null}
        {!loading && !error && reports.length === 0 ? (
          <View style={styles.empty} testID="explore-empty">
            <Text style={styles.emptyTitle}>{t('explore.emptyTitle')}</Text>
            <Text style={styles.muted}>{t('explore.empty')}</Text>
          </View>
        ) : null}
        {!loading && !error && reports.length > 0 ? (
          <View style={styles.publicContent}>
            <PublicReportFilters filters={filters} categories={categories} onChange={setFilters} />
            {filteredReports.length === 0 ? (
              <View style={styles.empty} testID="public-filter-empty">
                <Text style={styles.emptyTitle}>{t('explore.noMatchTitle')}</Text>
                <Text style={styles.muted}>{t('explore.noMatchBody')}</Text>
                <Button mode="outlined" onPress={() => setFilters(DEFAULT_FILTERS)}>
                  {t('explore.clearFilters')}
                </Button>
              </View>
            ) : (
              <>
                <PublicReportsMap reports={filteredReports} onOpenReport={openPublicReport} />
                {skippedCount > 0 ? (
                  <Text style={styles.mapNote} testID="public-map-skipped-count">
                    {skippedCount === 1
                      ? t('explore.skippedOne', { count: skippedCount })
                      : t('explore.skippedMany', { count: skippedCount })}
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
              accessibilityLabel={t('explore.openReport', { ticketNumber: report.ticketNumber })}
              onPress={() => openPublicReport(report.ticketNumber)}
              style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}
            >
              <ReportPhoto
                uri={report.photoUrl}
                accessibilityLabel={t('explore.photoAlt', { ticketNumber: report.ticketNumber })}
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
                    {t('explore.openLocation')}
                  </Button>
                ) : null}
                <Text
                  style={styles.attribution}
                  testID={`public-report-attribution-${report.ticketNumber}`}
                >
                  {t('explore.sharedBy', { name: report.attribution.displayName })}
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
  scroll: {
    paddingHorizontal: spacing[5],
    paddingTop: spacing[3],
    paddingBottom: 110,
    gap: spacing[5],
  },
  header: { gap: 2 },
  overline: { fontSize: 11, fontWeight: '700', letterSpacing: 1.05, color: colors.textMuted },
  title: {
    fontSize: 34,
    lineHeight: 40,
    fontWeight: '800',
    letterSpacing: -1.1,
    color: colors.text,
  },
  subtitle: {
    maxWidth: 340,
    marginTop: spacing[2],
    fontSize: 15,
    lineHeight: 22,
    color: colors.textSecondary,
  },
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
  },
  cardPressed: { backgroundColor: colors.brandSoft },
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

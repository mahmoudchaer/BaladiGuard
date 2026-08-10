import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { ActivityIndicator, Banner, Button, Text } from 'react-native-paper';
import { Link, useRouter, type Href } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useCitizenAuth } from '@/auth';
import { buildLoginHref } from '@/auth/returnTo';
import { BrandMark, BrandStripe } from '@/components/BrandMark';
import { ReportPhoto } from '@/components/ReportPhoto';
import { StatusChip } from '@/components/StatusChip';
import { PublicReportFilters } from '@/features/public-browse/PublicReportFilters';
import { PublicReportsMap } from '@/features/public-browse/PublicReportsMap';
import { getPublicTickets } from '@/services/api/tickets';
import { colors, radii, spacing, touchTargetMin, typography } from '@/theme';
import { formatCategoryLabel } from '@/theme/labels';
import type { PublicTicketResponse } from '@/types/ticket';
import { openInMapsApp } from '@/utils/openMaps';
import {
  filterPublicReports,
  partitionPlottableReports,
  uniquePublicCategories,
  type PublicBrowseFilters,
} from '@/utils/publicMapClustering';

const PUBLIC_FEED_LIMIT = 50;

const DEFAULT_FILTERS: PublicBrowseFilters = {
  status: 'ALL',
  category: 'ALL',
};

export default function HomeScreen() {
  const router = useRouter();
  const { isAuthenticated, contributionReady, profile, logout, isLoading } = useCitizenAuth();
  const [reports, setReports] = useState<PublicTicketResponse[]>([]);
  const [filters, setFilters] = useState<PublicBrowseFilters>(DEFAULT_FILTERS);
  const [isLoadingReports, setIsLoadingReports] = useState(true);
  const [reportError, setReportError] = useState<string | null>(null);
  const loadSeqRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  const loadReports = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const seq = ++loadSeqRef.current;

    setIsLoadingReports(true);
    setReportError(null);
    try {
      const response = await getPublicTickets({
        limit: PUBLIC_FEED_LIMIT,
        signal: controller.signal,
      });
      if (seq !== loadSeqRef.current) {
        return;
      }
      setReports(response.items);
    } catch (error) {
      if (seq !== loadSeqRef.current || controller.signal.aborted) {
        return;
      }
      setReportError(
        error instanceof Error ? error.message : 'Unable to load public reports right now.',
      );
    } finally {
      if (seq === loadSeqRef.current) {
        setIsLoadingReports(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadReports();
    return () => {
      loadSeqRef.current += 1;
      abortRef.current?.abort();
    };
  }, [loadReports]);

  const filteredReports = useMemo(() => filterPublicReports(reports, filters), [reports, filters]);

  const { skippedCount } = useMemo(
    () => partitionPlottableReports(filteredReports),
    [filteredReports],
  );

  const categories = useMemo(() => uniquePublicCategories(reports), [reports]);

  const openPublicReport = (ticketNumber: string) => {
    router.push({
      pathname: '/public/[ticketNumber]',
      params: { ticketNumber },
    } as unknown as Href);
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={styles.container}>
        <View style={styles.brandBlock}>
          <BrandStripe />
          <View style={styles.brandRow}>
            <BrandMark size={30} />
            <Text variant="headlineMedium" style={styles.title} accessibilityRole="header">
              BaladiGuard
            </Text>
          </View>
          <Text variant="bodyLarge" style={styles.subtitle}>
            Report infrastructure issues in your neighborhood and track municipal progress.
          </Text>
        </View>

        <View style={styles.actions}>
          <Link href="/report" asChild>
            <Button
              mode="contained"
              icon="clipboard-text-outline"
              style={styles.primaryButton}
              contentStyle={styles.primaryButtonContent}
              labelStyle={styles.primaryButtonLabel}
              buttonColor={colors.brand}
              textColor={colors.textInverse}
              elevation={0}
              accessibilityHint="Starts a new infrastructure report"
            >
              Report an issue
            </Button>
          </Link>
          <Link href={'/track' as Href} asChild>
            <Button
              mode="outlined"
              icon="magnify"
              style={styles.secondaryButton}
              contentStyle={styles.secondaryButtonContent}
              labelStyle={styles.secondaryButtonLabel}
              textColor={colors.brandDark}
              compact={false}
            >
              Track a report
            </Button>
          </Link>
        </View>

        {!isLoading && isAuthenticated ? (
          <View style={styles.sessionCard}>
            <Text variant="labelLarge" style={styles.sessionEyebrow}>
              Your account
            </Text>
            <Text variant="bodyMedium" style={styles.sessionText}>
              {contributionReady
                ? `Signed in as ${profile?.fullName ?? profile?.phone}`
                : `Signed in as ${profile?.fullName ?? profile?.phone}\nFinish setup in Profile to submit reports.`}
            </Text>
            <View style={styles.sessionActions}>
              <Link href={'/profile' as Href} asChild>
                <Button
                  mode="text"
                  compact
                  icon="account"
                  textColor={colors.brandDark}
                  style={styles.sessionButton}
                  testID="profile-entry-button"
                >
                  Profile
                </Button>
              </Link>
              <Link href={'/history' as Href} asChild>
                <Button
                  mode="text"
                  compact
                  icon="history"
                  textColor={colors.brandDark}
                  style={styles.sessionButton}
                  testID="history-entry-button"
                >
                  My reports
                </Button>
              </Link>
              <Button
                mode="text"
                compact
                onPress={() => void logout()}
                textColor={colors.textSecondary}
                style={styles.sessionButton}
                testID="logout-button"
              >
                Sign out
              </Button>
            </View>
          </View>
        ) : (
          <View style={styles.guestActions}>
            <Link href={buildLoginHref('/') as Href} asChild>
              <Button
                mode="text"
                icon="cellphone-message"
                textColor={colors.brandDark}
                style={styles.guestButton}
                contentStyle={styles.guestButtonContent}
                testID="sign-in-button"
              >
                Sign in with phone
              </Button>
            </Link>
            <Link href={'/privacy' as Href} asChild>
              <Button
                mode="text"
                textColor={colors.textSecondary}
                style={styles.guestButton}
                contentStyle={styles.guestButtonContent}
              >
                Privacy notice
              </Button>
            </Link>
          </View>
        )}

        <View style={styles.feedHeader}>
          <Text variant="titleMedium" style={styles.sectionTitle}>
            Public reports
          </Text>
          <Text variant="bodySmall" style={styles.feedHint}>
            Nearby issues shared without private contact details.
          </Text>
        </View>

        {reportError ? (
          <View style={styles.errorBlock}>
            <Banner visible icon="alert-circle" style={styles.errorBanner}>
              {reportError}
            </Banner>
            <Button mode="outlined" onPress={() => void loadReports()} textColor={colors.brandDark}>
              Try again
            </Button>
          </View>
        ) : null}

        {isLoadingReports ? (
          <View style={styles.reportLoading} testID="public-reports-loading">
            <ActivityIndicator color={colors.brand} />
            <Text variant="bodyMedium" style={styles.loadingText}>
              Loading public reports…
            </Text>
          </View>
        ) : (
          <View style={styles.publicContent} testID="public-report-feed">
            {reports.length > 0 ? (
              <PublicReportFilters
                filters={filters}
                categories={categories}
                onChange={setFilters}
              />
            ) : null}

            {reports.length === 0 && !reportError ? (
              <View style={styles.emptyState}>
                <Text variant="titleSmall" style={styles.emptyTitle}>
                  No public reports yet
                </Text>
                <Text variant="bodyMedium" style={styles.emptyBody}>
                  Be the first to report an infrastructure issue in your area.
                </Text>
              </View>
            ) : null}

            {reports.length > 0 && filteredReports.length === 0 ? (
              <View style={styles.emptyState} testID="public-filter-empty">
                <Text variant="titleSmall" style={styles.emptyTitle}>
                  No public reports match these filters
                </Text>
                <Text variant="bodyMedium" style={styles.emptyBody}>
                  Clear a status or category filter to see more of the public map and list.
                </Text>
                <Button
                  mode="outlined"
                  onPress={() => setFilters(DEFAULT_FILTERS)}
                  textColor={colors.brandDark}
                  testID="public-filter-clear"
                >
                  Clear filters
                </Button>
              </View>
            ) : null}

            {filteredReports.length > 0 ? (
              <>
                {skippedCount > 0 ? (
                  <Banner
                    visible
                    icon="map-marker-off"
                    style={styles.partialBanner}
                    testID="public-map-partial-data"
                  >
                    {skippedCount === 1
                      ? '1 public report is missing a map position and is list-only.'
                      : `${skippedCount} public reports are missing map positions and are list-only.`}
                  </Banner>
                ) : null}
                <PublicReportsMap reports={filteredReports} onOpenReport={openPublicReport} />
              </>
            ) : null}

            {filteredReports.length > 0 ? (
              <View
                style={styles.listSection}
                testID="public-report-list"
                accessibilityRole="summary"
                accessibilityLabel="Public report list alternative to the map"
              >
                <Text variant="titleSmall" style={styles.listTitle}>
                  Report list
                </Text>
                <Text variant="bodySmall" style={styles.feedHint}>
                  Full list of the same citizen-safe public reports shown on the map.
                </Text>
              </View>
            ) : null}

            {filteredReports.map((report) => (
              <View key={report.ticketNumber} style={styles.reportRow}>
                <Pressable
                  style={({ pressed }) => [
                    styles.reportPressable,
                    pressed && styles.reportRowPressed,
                  ]}
                  onPress={() => openPublicReport(report.ticketNumber)}
                  testID={`public-report-card-${report.ticketNumber}`}
                  accessibilityRole="button"
                  accessibilityLabel={`Open public report ${report.ticketNumber}`}
                >
                  <View style={styles.reportBody}>
                    <ReportPhoto
                      uri={report.photoUrl}
                      accessibilityLabel={`Photo for report ${report.ticketNumber}`}
                      testID={`public-report-photo-${report.ticketNumber}`}
                      variant="compact"
                    />
                    <View style={styles.reportMain}>
                      <View style={styles.reportCardHeader}>
                        <Text variant="titleSmall" style={styles.reportNumber}>
                          {report.ticketNumber}
                        </Text>
                        <StatusChip status={report.status} />
                      </View>
                      <Text variant="bodyMedium" style={styles.reportDescription} numberOfLines={3}>
                        {report.description}
                      </Text>
                      <Text variant="bodySmall" style={styles.metaText}>
                        {formatCategoryLabel(report.category)} · {report.location.addressText}
                      </Text>
                      <Text variant="bodySmall" style={styles.metaText}>
                        Reported by {report.attribution.displayName}
                      </Text>
                    </View>
                  </View>
                </Pressable>
                <Button
                  mode="outlined"
                  compact
                  icon="map-marker-outline"
                  style={styles.mapsButton}
                  contentStyle={styles.mapsButtonContent}
                  labelStyle={styles.mapsButtonLabel}
                  textColor={colors.brandDark}
                  disabled={
                    !Number.isFinite(report.mapLocation?.latitude) ||
                    !Number.isFinite(report.mapLocation?.longitude)
                  }
                  onPress={() => {
                    void openInMapsApp({
                      latitude: report.mapLocation.latitude,
                      longitude: report.mapLocation.longitude,
                      label: report.mapLocation.addressText || report.ticketNumber,
                    });
                  }}
                  testID={`public-report-maps-${report.ticketNumber}`}
                  accessibilityLabel={`Open ${report.ticketNumber} location in maps`}
                >
                  Open in Maps
                </Button>
              </View>
            ))}
          </View>
        )}
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
  brandBlock: {
    gap: spacing[2],
    paddingBottom: spacing[1],
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing[2],
  },
  title: {
    fontWeight: '700',
    color: colors.brandDark,
    fontSize: typography.pageTitle,
    flexShrink: 1,
    letterSpacing: -0.4,
  },
  subtitle: {
    color: colors.textSecondary,
    lineHeight: 22,
  },
  actions: {
    gap: spacing[3],
  },
  primaryButton: {
    borderRadius: radii.lg,
    backgroundColor: colors.brand,
  },
  primaryButtonContent: {
    minHeight: touchTargetMin,
  },
  primaryButtonLabel: {
    fontSize: typography.control,
    fontWeight: '700',
  },
  secondaryButton: {
    borderRadius: radii.lg,
    borderColor: colors.brand,
    backgroundColor: colors.surface,
  },
  secondaryButtonContent: {
    minHeight: touchTargetMin,
  },
  secondaryButtonLabel: {
    fontSize: typography.control,
    fontWeight: '700',
  },
  sessionCard: {
    gap: spacing[2],
    padding: spacing[4],
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  sessionEyebrow: {
    color: colors.brandDark,
    fontWeight: '700',
    letterSpacing: 0.3,
    textTransform: 'uppercase',
    fontSize: typography.label,
  },
  sessionText: {
    color: colors.textSecondary,
  },
  sessionActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: -spacing[1],
  },
  sessionButton: {
    minHeight: touchTargetMin,
    justifyContent: 'center',
  },
  guestActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing[1],
  },
  guestButton: {
    minHeight: touchTargetMin,
    justifyContent: 'center',
  },
  guestButtonContent: {
    minHeight: touchTargetMin,
  },
  feedHeader: {
    gap: spacing[1],
    marginTop: spacing[3],
    paddingTop: spacing[2],
  },
  sectionTitle: {
    fontWeight: '700',
    color: colors.text,
    fontSize: typography.sectionTitle,
    letterSpacing: -0.2,
  },
  feedHint: {
    color: colors.textMuted,
  },
  errorBlock: {
    gap: spacing[3],
  },
  errorBanner: {
    backgroundColor: colors.dangerSoft,
  },
  partialBanner: {
    backgroundColor: colors.warningSoft,
  },
  reportLoading: {
    minHeight: 120,
    justifyContent: 'center',
    alignItems: 'center',
    gap: spacing[2],
  },
  loadingText: {
    color: colors.textSecondary,
  },
  publicContent: {
    gap: spacing[3],
  },
  emptyState: {
    padding: spacing[4],
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderStyle: 'dashed',
    backgroundColor: colors.surface,
    gap: spacing[2],
  },
  emptyTitle: {
    fontWeight: '700',
    color: colors.text,
  },
  emptyBody: {
    color: colors.textSecondary,
  },
  listSection: {
    gap: spacing[1],
    marginTop: spacing[1],
  },
  listTitle: {
    fontWeight: '700',
    color: colors.text,
  },
  reportRow: {
    gap: spacing[3],
    padding: spacing[3],
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    shadowColor: '#1a2332',
    shadowOpacity: 0.05,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 1,
  },
  reportPressable: {
    borderRadius: radii.md,
    minHeight: touchTargetMin,
  },
  reportRowPressed: {
    backgroundColor: colors.brandSoft,
  },
  reportBody: {
    flexDirection: 'row',
    gap: spacing[3],
    alignItems: 'flex-start',
  },
  reportMain: {
    flex: 1,
    gap: spacing[1],
    minWidth: 0,
  },
  reportCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: spacing[3],
  },
  reportNumber: {
    color: colors.text,
    fontWeight: '700',
    flexShrink: 1,
  },
  reportDescription: {
    color: colors.text,
    lineHeight: 21,
  },
  metaText: {
    color: colors.textMuted,
  },
  mapsButton: {
    borderColor: colors.borderStrong,
    borderRadius: radii.md,
    alignSelf: 'stretch',
  },
  mapsButtonContent: {
    minHeight: 40,
  },
  mapsButtonLabel: {
    fontSize: typography.metadata,
    fontWeight: '700',
  },
});

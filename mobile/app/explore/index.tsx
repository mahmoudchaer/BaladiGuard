import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { Banner, Button, Text } from 'react-native-paper';
import { useRouter, type Href } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useCitizenAuth } from '@/auth';
import { AppBottomNavigation } from '@/components/AppBottomNavigation';
import { BrandMark } from '@/components/BrandMark';
import { ReportPhoto } from '@/components/ReportPhoto';
import { StatusChip } from '@/components/StatusChip';
import { getPublicTickets } from '@/services/api/tickets';
import { colors, radii, spacing, touchTargetMin } from '@/theme';
import { formatCategoryLabel } from '@/theme/labels';
import type { PublicTicketResponse } from '@/types/ticket';

export default function ExploreScreen() {
  const router = useRouter();
  const { isAuthenticated } = useCitizenAuth();
  const [reports, setReports] = useState<PublicTicketResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setReports((await getPublicTickets({ limit: 20 })).items);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load community reports.');
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

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
        <View style={styles.list} testID="public-report-feed">
          {reports.map((report) => (
            <Pressable
              key={report.ticketNumber}
              testID={`public-report-card-${report.ticketNumber}`}
              accessibilityRole="button"
              accessibilityLabel={`Open public report ${report.ticketNumber}`}
              onPress={() =>
                router.push({
                  pathname: '/public/[ticketNumber]',
                  params: { ticketNumber: report.ticketNumber },
                } as unknown as Href)
              }
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
      {isAuthenticated ? <AppBottomNavigation active="explore" /> : null}
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

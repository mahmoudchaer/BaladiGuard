import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { Button, Text } from 'react-native-paper';
import { Link, useRouter, type Href } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useCitizenAuth } from '@/auth';
import { buildLoginHref } from '@/auth/returnTo';
import { BrandMark, BrandStripe } from '@/components/BrandMark';
import { StatusChip } from '@/components/StatusChip';
import { getCitizenTicketHistory } from '@/services/api/tickets';
import { colors, radii, spacing, typography } from '@/theme';
import { formatCategoryLabel } from '@/theme/labels';
import type { CitizenTicketHistoryItem } from '@/types/ticket';

export default function HomeScreen() {
  const router = useRouter();
  const { accessToken, isAuthenticated, isLoading, profile } = useCitizenAuth();
  const [reports, setReports] = useState<CitizenTicketHistoryItem[]>([]);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState(false);

  const loadSummary = useCallback(async () => {
    if (!accessToken) return;
    setSummaryLoading(true);
    setSummaryError(false);
    try {
      const page = await getCitizenTicketHistory({ accessToken, limit: 3 });
      setReports(page.items);
    } catch {
      setSummaryError(true);
    } finally {
      setSummaryLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    if (isAuthenticated) void loadSummary();
  }, [isAuthenticated, loadSummary]);

  if (isLoading) {
    return (
      <SafeAreaView style={styles.splash} testID="session-loading-splash">
        <BrandStripe />
        <BrandMark size={58} />
        <Text style={styles.splashTitle}>BaladiGuard</Text>
        <Text style={styles.splashText}>Your community, cared for.</Text>
        <ActivityIndicator color={colors.brand} style={styles.splashSpinner} />
      </SafeAreaView>
    );
  }

  if (!isAuthenticated) {
    return (
      <SafeAreaView style={styles.safeArea} testID="welcome-screen">
        <ScrollView contentContainerStyle={styles.welcome}>
          <View style={styles.welcomeBrand}>
            <BrandStripe />
            <View style={styles.wordmark}>
              <BrandMark size={42} />
              <Text style={styles.brandName}>BaladiGuard</Text>
            </View>
          </View>
          <View style={styles.hero}>
            <Text style={styles.eyebrow}>A better way to care for your city</Text>
            <Text style={styles.heroTitle} accessibilityRole="header">
              See it. Report it. Follow the progress.
            </Text>
            <Text style={styles.heroBody}>
              Report local infrastructure issues and stay informed as your municipality responds.
            </Text>
          </View>
          <View style={styles.welcomeActions}>
            <Link href={buildLoginHref('/') as Href} asChild>
              <Button
                mode="contained"
                icon="cellphone-check"
                contentStyle={styles.buttonContent}
                buttonColor={colors.brand}
                testID="sign-in-button"
              >
                Sign in or create an account
              </Button>
            </Link>
            <Link href={'/explore' as Href} asChild>
              <Button
                mode="outlined"
                icon="compass-outline"
                contentStyle={styles.buttonContent}
                textColor={colors.brandDark}
                testID="continue-as-guest"
              >
                Continue as guest
              </Button>
            </Link>
          </View>
          <View style={styles.steps}>
            {[
              ['1', 'Spot an issue', 'Roads, lighting, waste, water, and more.'],
              ['2', 'Send a clear report', 'Add a photo and location in a few simple steps.'],
              ['3', 'Follow the response', 'See public progress or track with your private code.'],
            ].map(([number, title, body]) => (
              <View style={styles.step} key={number}>
                <View style={styles.stepNumber}>
                  <Text style={styles.stepNumberText}>{number}</Text>
                </View>
                <View style={styles.stepCopy}>
                  <Text style={styles.stepTitle}>{title}</Text>
                  <Text style={styles.stepBody}>{body}</Text>
                </View>
              </View>
            ))}
          </View>
          <Text style={styles.accountNote}>
            A verified phone number is only needed to submit reports. Browsing and tracking stay
            open to everyone, and you can add your name later if you want.
          </Text>
          <View style={styles.guestLinks}>
            <Link href={'/track' as Href} asChild>
              <Button mode="text" compact textColor={colors.brandDark}>
                Track with a code
              </Button>
            </Link>
            <Link href={'/privacy' as Href} asChild>
              <Button mode="text" compact textColor={colors.brandDark}>
                Privacy notice
              </Button>
            </Link>
          </View>
        </ScrollView>
      </SafeAreaView>
    );
  }

  const firstName = profile?.fullName?.trim().split(/\s+/)[0];
  const activeCount = reports.filter(
    (report) => !['RESOLVED', 'CLOSED'].includes(report.status),
  ).length;
  return (
    <SafeAreaView style={styles.safeArea} edges={['top', 'left', 'right']} testID="signed-in-home">
      <ScrollView contentContainerStyle={styles.home}>
        <View style={styles.homeHeader}>
          <View>
            <Text style={styles.eyebrow}>WELCOME BACK</Text>
            <Text style={styles.homeTitle}>{firstName ? `Hello, ${firstName}` : 'Hello'}</Text>
          </View>
          <BrandMark size={34} />
        </View>
        <View style={styles.reportCard}>
          <Text style={styles.reportCardTitle}>Something needs attention?</Text>
          <Text style={styles.reportCardBody}>
            A clear photo and location help your municipality respond faster.
          </Text>
          <Button
            mode="contained"
            icon="plus"
            onPress={() => router.push('/report' as Href)}
            contentStyle={styles.buttonContent}
            buttonColor={colors.brandDark}
          >
            Report an issue
          </Button>
        </View>
        <View style={styles.sectionHeader}>
          <View>
            <Text style={styles.sectionTitle}>Your reports</Text>
            <Text style={styles.sectionHint}>
              {summaryLoading
                ? 'Checking for updates…'
                : reports.length
                  ? `${activeCount} active · ${reports.length} recent`
                  : 'Recent account activity'}
            </Text>
          </View>
          <Button
            mode="text"
            compact
            onPress={() => router.push('/history' as Href)}
            textColor={colors.brandDark}
          >
            View all
          </Button>
        </View>
        {summaryError ? (
          <View style={styles.stateCard} testID="home-summary-error">
            <Text style={styles.stateTitle}>Updates are unavailable</Text>
            <Text style={styles.stateBody}>
              Your reports are safe. Check your connection and try again.
            </Text>
            <Button mode="text" onPress={() => void loadSummary()}>
              Try again
            </Button>
          </View>
        ) : null}
        {!summaryLoading && !summaryError && reports.length === 0 ? (
          <View style={styles.stateCard} testID="home-summary-empty">
            <Text style={styles.stateTitle}>Your first report starts here</Text>
            <Text style={styles.stateBody}>
              Reports sent from this account will appear here with their latest status.
            </Text>
          </View>
        ) : null}
        {reports.map((report) => (
          <Pressable
            style={({ pressed }) => [styles.reportRow, pressed && styles.reportRowPressed]}
            key={report.trackingCode}
            accessibilityRole="button"
            accessibilityLabel={`Open report ${report.trackingCode}`}
            onPress={() =>
              router.push({ pathname: '/track', params: { trackingCode: report.trackingCode } })
            }
          >
            <View style={styles.rowTop}>
              <Text style={styles.rowTitle} numberOfLines={1}>
                {formatCategoryLabel(report.category)}
              </Text>
              <StatusChip status={report.status} />
            </View>
            <Text style={styles.rowBody} numberOfLines={1}>
              {report.locationAddress}
            </Text>
            <Text style={styles.rowMeta}>
              Submitted{' '}
              {new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(
                new Date(report.submittedAt),
              )}
            </Text>
          </Pressable>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.background },
  splash: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surface,
    padding: spacing[6],
  },
  splashTitle: { marginTop: spacing[4], fontSize: 30, fontWeight: '800', color: colors.text },
  splashText: { marginTop: spacing[2], fontSize: 16, color: colors.textSecondary },
  splashSpinner: { marginTop: spacing[8] },
  welcome: {
    flexGrow: 1,
    paddingHorizontal: spacing[5],
    paddingTop: spacing[5],
    paddingBottom: spacing[6],
    gap: spacing[5],
  },
  welcomeBrand: { alignItems: 'flex-start' },
  wordmark: { flexDirection: 'row', alignItems: 'center', gap: spacing[3] },
  brandName: { fontSize: 25, fontWeight: '800', color: colors.text },
  hero: { gap: spacing[3] },
  eyebrow: { fontSize: 12, fontWeight: '800', letterSpacing: 1.1, color: colors.brandDark },
  heroTitle: {
    fontSize: 34,
    lineHeight: 40,
    fontWeight: '800',
    color: colors.text,
    letterSpacing: -0.7,
  },
  heroBody: { fontSize: 17, lineHeight: 25, color: colors.textSecondary },
  welcomeActions: { gap: spacing[3] },
  buttonContent: { minHeight: 50 },
  steps: {
    padding: spacing[4],
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    gap: spacing[4],
    borderWidth: 1,
    borderColor: colors.border,
  },
  step: { flexDirection: 'row', gap: spacing[3], alignItems: 'center' },
  stepNumber: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.brandSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepNumberText: { fontWeight: '800', color: colors.brandDark },
  stepCopy: { flex: 1 },
  stepTitle: { fontSize: 15, fontWeight: '700', color: colors.text },
  stepBody: { marginTop: 2, fontSize: 13, lineHeight: 18, color: colors.textSecondary },
  accountNote: { fontSize: 13, lineHeight: 19, textAlign: 'center', color: colors.textMuted },
  guestLinks: { flexDirection: 'row', justifyContent: 'center', flexWrap: 'wrap' },
  home: { padding: spacing[5], paddingBottom: spacing[8], gap: spacing[5] },
  homeHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  homeTitle: {
    marginTop: spacing[1],
    fontSize: typography.pageTitle,
    fontWeight: '800',
    color: colors.text,
  },
  reportCard: {
    padding: spacing[5],
    gap: spacing[3],
    borderRadius: 16,
    backgroundColor: colors.brand,
    shadowColor: '#000',
    shadowOpacity: 0.1,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 5 },
    elevation: 3,
  },
  reportCardTitle: { fontSize: 21, fontWeight: '800', color: colors.textInverse },
  reportCardBody: { fontSize: 15, lineHeight: 22, color: '#E6F4EC' },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  sectionTitle: { fontSize: 19, fontWeight: '800', color: colors.text },
  sectionHint: { marginTop: 3, fontSize: 13, color: colors.textSecondary },
  stateCard: {
    padding: spacing[5],
    alignItems: 'center',
    gap: spacing[2],
    borderRadius: radii.lg,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  stateTitle: { fontSize: 16, fontWeight: '700', color: colors.text },
  stateBody: { textAlign: 'center', lineHeight: 20, color: colors.textSecondary },
  reportRow: {
    padding: spacing[4],
    gap: spacing[2],
    borderRadius: radii.lg,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  reportRowPressed: { backgroundColor: colors.brandSoft, borderColor: colors.brand },
  rowTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: spacing[2],
  },
  rowTitle: { flex: 1, fontSize: 15, fontWeight: '700', color: colors.text },
  rowBody: { fontSize: 13, color: colors.textSecondary },
  rowMeta: { fontSize: 12, color: colors.textMuted },
});

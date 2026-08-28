import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, View } from 'react-native';
import { Icon, Text } from 'react-native-paper';
import { Link, useRouter, type Href } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useCitizenAuth } from '@/auth';
import { buildLoginHref } from '@/auth/returnTo';
import { BrandMark } from '@/components/BrandMark';
import { CivicIllustration } from '@/components/CivicIllustration';
import { useI18n } from '@/i18n/LocaleProvider';
import { StatusChip } from '@/components/StatusChip';
import { TactilePressable } from '@/components/TactilePressable';
import { getCitizenTicketHistory } from '@/services/api/tickets';
import { colors, radii, shadows, spacing, typography } from '@/theme';
import { formatCategoryLabel } from '@/theme/labels';
import type { CitizenTicketHistoryItem } from '@/types/ticket';

type ActionProps = {
  icon: string;
  label: string;
  detail?: string;
  onPress?: () => void;
  primary?: boolean;
  testID?: string;
};

function Action({ icon, label, detail, onPress, primary = false, testID }: ActionProps) {
  return (
    <TactilePressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      testID={testID}
      style={[styles.action, primary && styles.primaryAction]}
    >
      <View style={[styles.actionIcon, primary && styles.primaryActionIcon]}>
        <Icon source={icon} size={22} color={primary ? colors.brand : colors.brandDark} />
      </View>
      <View style={styles.actionCopy}>
        <Text style={[styles.actionLabel, primary && styles.primaryActionLabel]}>{label}</Text>
        {detail ? (
          <Text style={[styles.actionDetail, primary && styles.primaryActionDetail]}>{detail}</Text>
        ) : null}
      </View>
      <Icon source="chevron-right" size={21} color={primary ? '#C8E9D7' : colors.textMuted} />
    </TactilePressable>
  );
}

export default function HomeScreen() {
  const { t } = useI18n();
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
        <View style={styles.splashMark}>
          <BrandMark size={54} />
        </View>
        <Text style={styles.splashTitle}>BaladiGuard</Text>
        <ActivityIndicator color={colors.brand} style={styles.splashSpinner} />
      </SafeAreaView>
    );
  }

  if (!isAuthenticated) {
    return (
      <SafeAreaView style={styles.safeArea} testID="welcome-screen">
        <ScrollView contentContainerStyle={styles.welcome} showsVerticalScrollIndicator={false}>
          <View style={styles.brandRow}>
            <BrandMark size={38} />
            <Text style={styles.brandName}>BaladiGuard</Text>
          </View>

          <View style={styles.welcomeHero}>
            <Text style={styles.heroTitle} accessibilityRole="header">
              {t('home.heroTitle')}
            </Text>
            <Text style={styles.heroBody}>{t('home.heroBody')}</Text>
          </View>

          <View style={styles.heroSymbol} accessibilityElementsHidden>
            <CivicIllustration name="citizen-reporting" style={styles.heroArtwork} />
            <View style={styles.heroStatus}>
              <View style={styles.liveDot} />
              <Text style={styles.heroStatusText}>{t('home.builtFor')}</Text>
            </View>
          </View>

          <View style={styles.welcomeActions}>
            <Link href={buildLoginHref('/') as Href} asChild>
              <TactilePressable
                accessibilityRole="button"
                testID="sign-in-button"
                style={styles.signInButton}
              >
                <Text style={styles.signInText}>{t('home.signInCreate')}</Text>
                <Icon source="arrow-right" size={21} color={colors.textInverse} />
              </TactilePressable>
            </Link>
            <Link href={'/explore' as Href} asChild>
              <TactilePressable
                accessibilityRole="button"
                testID="continue-as-guest"
                style={styles.guestButton}
              >
                <Icon source="compass-outline" size={21} color={colors.brandDark} />
                <Text style={styles.guestText}>{t('home.continueGuest')}</Text>
              </TactilePressable>
            </Link>
          </View>

          <View style={styles.welcomeFooter}>
            <Link href={'/track' as Href} asChild>
              <TactilePressable style={styles.footerLink} accessibilityRole="button">
                <Text style={styles.footerLinkText}>{t('home.trackCode')}</Text>
              </TactilePressable>
            </Link>
            <View style={styles.footerDot} />
            <Link href={'/privacy' as Href} asChild>
              <TactilePressable style={styles.footerLink} accessibilityRole="button">
                <Text style={styles.footerLinkText}>{t('home.privacy')}</Text>
              </TactilePressable>
            </Link>
          </View>
          <Text style={styles.accountNote}>{t('home.phoneHint')}</Text>
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
      <ScrollView contentContainerStyle={styles.home} showsVerticalScrollIndicator={false}>
        <View style={styles.homeHeader}>
          <View>
            <Text style={styles.overline}>{greeting(t)}</Text>
            <Text style={styles.homeTitle}>
              {firstName ? t('home.helloName', { name: firstName }) : t('home.hello')}
            </Text>
          </View>
          <TactilePressable
            accessibilityRole="button"
            accessibilityLabel={t('a11y.openProfile')}
            onPress={() => router.push('/profile' as Href)}
            style={styles.avatar}
          >
            <Text style={styles.avatarText}>{firstName?.[0]?.toUpperCase() || 'B'}</Text>
          </TactilePressable>
        </View>

        <Action
          primary
          icon="plus"
          label={t('home.reportIssue')}
          detail={t('home.reportHint')}
          onPress={() => router.push('/report' as Href)}
        />

        <View style={styles.quickActions}>
          <TactilePressable
            onPress={() => router.push('/track' as Href)}
            accessibilityRole="button"
            style={styles.quickAction}
          >
            <View style={styles.quickIcon}>
              <Icon source="barcode-scan" size={23} color={colors.brandDark} />
            </View>
            <Text style={styles.quickTitle}>{t('home.trackCode')}</Text>
            <Text style={styles.quickDetail}>{t('home.trackHint')}</Text>
          </TactilePressable>
          <TactilePressable
            onPress={() => router.push('/explore' as Href)}
            accessibilityRole="button"
            style={styles.quickAction}
          >
            <View style={styles.quickIcon}>
              <Icon source="map-outline" size={23} color={colors.brandDark} />
            </View>
            <Text style={styles.quickTitle}>{t('home.nearby')}</Text>
            <Text style={styles.quickDetail}>{t('home.browseReports')}</Text>
          </TactilePressable>
        </View>

        <View style={styles.sectionHeader}>
          <View>
            <Text style={styles.sectionTitle}>{t('home.yourReports')}</Text>
            <Text style={styles.sectionHint}>
              {summaryLoading
                ? t('home.checkingUpdates')
                : reports.length
                  ? t('home.activeCount', { count: activeCount })
                  : t('home.yourActivity')}
            </Text>
          </View>
          <TactilePressable
            onPress={() => router.push('/history' as Href)}
            style={styles.seeAll}
            accessibilityRole="button"
          >
            <Text style={styles.seeAllText}>{t('home.viewAll')}</Text>
          </TactilePressable>
        </View>

        {summaryError ? (
          <View style={styles.stateCard} testID="home-summary-error">
            <View style={styles.stateIcon}>
              <Icon source="wifi-alert" size={24} color={colors.warning} />
            </View>
            <View style={styles.stateCopy}>
              <Text style={styles.stateTitle}>{t('home.refreshFailedTitle')}</Text>
              <Text style={styles.stateBody}>{t('home.refreshFailedBody')}</Text>
            </View>
            <TactilePressable onPress={() => void loadSummary()}>
              <Text style={styles.retryText}>{t('common.retry')}</Text>
            </TactilePressable>
          </View>
        ) : null}

        {!summaryLoading && !summaryError && reports.length === 0 ? (
          <View style={styles.emptyState} testID="home-summary-empty">
            <CivicIllustration name="report-clipboard" style={styles.emptyArtwork} />
            <Text style={styles.emptyTitle}>{t('home.emptyTitle')}</Text>
            <Text style={styles.emptyBody}>{t('home.emptyBody')}</Text>
          </View>
        ) : null}

        {reports.length > 0 ? (
          <View style={styles.reportList}>
            {reports.map((report, index) => (
              <TactilePressable
                key={report.trackingCode}
                accessibilityRole="button"
                accessibilityLabel={t('home.openReport', { code: report.trackingCode })}
                onPress={() =>
                  router.push({ pathname: '/track', params: { trackingCode: report.trackingCode } })
                }
                style={[styles.reportRow, index > 0 && styles.reportDivider]}
                pressedScale={0.99}
              >
                <View style={styles.reportGlyph}>
                  <Icon source="map-marker-outline" size={21} color={colors.brandDark} />
                </View>
                <View style={styles.reportCopy}>
                  <Text style={styles.rowTitle} numberOfLines={1}>
                    {formatCategoryLabel(report.category)}
                  </Text>
                  <Text style={styles.rowBody} numberOfLines={1}>
                    {report.locationAddress}
                  </Text>
                </View>
                <View style={styles.reportTrailing}>
                  <StatusChip status={report.status} />
                  <Icon source="chevron-right" size={18} color={colors.textMuted} />
                </View>
              </TactilePressable>
            ))}
          </View>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

function greeting(translate: (key: string) => string) {
  const hour = new Date().getHours();
  if (hour < 12) return translate('home.morning');
  if (hour < 18) return translate('home.afternoon');
  return translate('home.evening');
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.background },
  splash: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
  },
  splashMark: {
    width: 86,
    height: 86,
    borderRadius: 26,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surface,
    ...shadows.medium,
  },
  splashTitle: {
    marginTop: spacing[5],
    fontSize: 25,
    fontWeight: '700',
    letterSpacing: -0.6,
    color: colors.text,
  },
  splashSpinner: { marginTop: spacing[8] },
  welcome: {
    flexGrow: 1,
    paddingHorizontal: spacing[5],
    paddingTop: spacing[3],
    paddingBottom: spacing[6],
  },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: spacing[3] },
  brandName: { fontSize: 22, fontWeight: '700', letterSpacing: -0.5, color: colors.text },
  welcomeHero: { marginTop: spacing[8], gap: spacing[3] },
  heroTitle: {
    maxWidth: 340,
    fontSize: 42,
    lineHeight: 45,
    fontWeight: '800',
    letterSpacing: -1.7,
    color: colors.text,
  },
  heroBody: {
    maxWidth: 350,
    fontSize: 17,
    lineHeight: 25,
    letterSpacing: -0.15,
    color: colors.textSecondary,
  },
  heroSymbol: {
    height: 220,
    marginVertical: spacing[5],
    alignItems: 'center',
    justifyContent: 'center',
  },
  heroArtwork: { width: '100%', height: 220 },
  heroSymbolGlow: {
    position: 'absolute',
    width: 174,
    height: 174,
    borderRadius: 87,
    backgroundColor: colors.brandSoft,
  },
  heroSymbolCircle: {
    width: 118,
    height: 118,
    borderRadius: 36,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.brand,
    transform: [{ rotate: '-4deg' }],
    ...shadows.large,
  },
  heroStatus: {
    position: 'absolute',
    bottom: 7,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing[2],
    paddingHorizontal: spacing[3],
    height: 34,
    borderRadius: radii.pill,
    backgroundColor: 'rgba(255,255,255,0.94)',
    ...shadows.small,
  },
  liveDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: colors.brand },
  heroStatusText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  welcomeActions: { gap: spacing[3] },
  signInButton: {
    minHeight: 58,
    paddingHorizontal: spacing[5],
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderRadius: radii.lg,
    backgroundColor: colors.brand,
  },
  signInText: { fontSize: 17, fontWeight: '700', letterSpacing: -0.2, color: colors.textInverse },
  guestButton: {
    minHeight: 54,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing[2],
    borderRadius: radii.lg,
    backgroundColor: colors.surface,
  },
  guestText: { fontSize: 16, fontWeight: '600', color: colors.brandDark },
  welcomeFooter: {
    marginTop: spacing[6],
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  footerLink: { minHeight: 44, paddingHorizontal: spacing[2], justifyContent: 'center' },
  footerLinkText: { fontSize: 14, fontWeight: '600', color: colors.brandDark },
  footerDot: {
    width: 3,
    height: 3,
    borderRadius: 2,
    marginHorizontal: spacing[2],
    backgroundColor: colors.borderStrong,
  },
  accountNote: { textAlign: 'center', fontSize: 12, lineHeight: 17, color: colors.textMuted },
  home: {
    paddingHorizontal: spacing[5],
    paddingTop: spacing[3],
    paddingBottom: 110,
    gap: spacing[5],
  },
  homeHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing[1],
  },
  overline: {
    fontSize: 11,
    lineHeight: 15,
    fontWeight: '700',
    letterSpacing: 1.05,
    color: colors.textMuted,
  },
  homeTitle: {
    marginTop: 2,
    fontSize: 34,
    lineHeight: 39,
    fontWeight: '800',
    letterSpacing: -1.1,
    color: colors.text,
  },
  avatar: {
    width: 46,
    height: 46,
    borderRadius: 23,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.brandSoft,
  },
  avatarText: { fontSize: 18, fontWeight: '700', color: colors.brandDark },
  action: {
    minHeight: 78,
    padding: spacing[4],
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing[3],
    borderRadius: radii.lg,
    backgroundColor: colors.surface,
  },
  primaryAction: { backgroundColor: colors.brand, ...shadows.medium },
  actionIcon: {
    width: 42,
    height: 42,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.brandSoft,
  },
  primaryActionIcon: { backgroundColor: colors.textInverse },
  actionCopy: { flex: 1, gap: 2 },
  actionLabel: { fontSize: 17, fontWeight: '700', letterSpacing: -0.25, color: colors.text },
  primaryActionLabel: { color: colors.textInverse },
  actionDetail: { fontSize: 13, color: colors.textSecondary },
  primaryActionDetail: { color: '#C8E9D7' },
  quickActions: { flexDirection: 'row', gap: spacing[3] },
  quickAction: {
    flex: 1,
    minHeight: 126,
    padding: spacing[4],
    borderRadius: radii.lg,
    backgroundColor: colors.surface,
  },
  quickIcon: {
    width: 40,
    height: 40,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.brandSoft,
  },
  quickTitle: { marginTop: spacing[3], fontSize: 15, fontWeight: '700', color: colors.text },
  quickDetail: { marginTop: 2, fontSize: 12, lineHeight: 16, color: colors.textMuted },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing[2],
  },
  sectionTitle: {
    fontSize: typography.sectionTitle,
    fontWeight: '700',
    letterSpacing: -0.35,
    color: colors.text,
  },
  sectionHint: { marginTop: 2, fontSize: 12, color: colors.textMuted },
  seeAll: { minHeight: 44, paddingHorizontal: spacing[2], justifyContent: 'center' },
  seeAllText: { fontSize: 14, fontWeight: '600', color: colors.brandDark },
  stateCard: {
    minHeight: 76,
    padding: spacing[3],
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing[3],
    borderRadius: radii.lg,
    backgroundColor: colors.surface,
  },
  stateIcon: {
    width: 42,
    height: 42,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.warningSoft,
  },
  stateCopy: { flex: 1 },
  stateTitle: { fontSize: 15, fontWeight: '700', color: colors.text },
  stateBody: { marginTop: 2, fontSize: 12, lineHeight: 16, color: colors.textSecondary },
  retryText: { padding: spacing[2], fontSize: 14, fontWeight: '700', color: colors.brandDark },
  emptyState: {
    padding: spacing[6],
    alignItems: 'center',
    borderRadius: radii.lg,
    backgroundColor: colors.surface,
  },
  emptyArtwork: { width: 138, height: 112 },
  emptyIcon: {
    width: 52,
    height: 52,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.brandSoft,
  },
  emptyTitle: { marginTop: spacing[3], fontSize: 16, fontWeight: '700', color: colors.text },
  emptyBody: {
    maxWidth: 250,
    marginTop: spacing[1],
    textAlign: 'center',
    fontSize: 13,
    lineHeight: 19,
    color: colors.textSecondary,
  },
  reportList: {
    overflow: 'hidden',
    paddingHorizontal: spacing[4],
    borderRadius: radii.lg,
    backgroundColor: colors.surface,
  },
  reportRow: { minHeight: 76, flexDirection: 'row', alignItems: 'center', gap: spacing[3] },
  reportDivider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  reportGlyph: {
    width: 38,
    height: 38,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.brandSoft,
  },
  reportCopy: { flex: 1, gap: 3 },
  rowTitle: { fontSize: 15, fontWeight: '600', color: colors.text },
  rowBody: { fontSize: 12, color: colors.textMuted },
  reportTrailing: { flexDirection: 'row', alignItems: 'center', gap: spacing[1] },
});

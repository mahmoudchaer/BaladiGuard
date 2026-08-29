import { ActivityIndicator, Alert, ScrollView, StyleSheet, View } from 'react-native';
import { Icon, Text } from 'react-native-paper';
import { Redirect, useRouter, type Href } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useCitizenAuth } from '@/auth';
import { buildLoginHref } from '@/auth/returnTo';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { TactilePressable } from '@/components/TactilePressable';
import { useI18n } from '@/i18n/LocaleProvider';
import { draftHasRestorableContent, loadReportDraft } from '@/services/reportDraft';
import { colors, radii, spacing } from '@/theme';

type MenuRowProps = {
  icon: string;
  label: string;
  detail?: string;
  onPress: () => void;
  destructive?: boolean;
  divider?: boolean;
  testID?: string;
};

function MenuRow({ icon, label, detail, onPress, destructive, divider, testID }: MenuRowProps) {
  const { isRtl } = useI18n();
  const tint = destructive ? colors.danger : colors.brandDark;
  return (
    <TactilePressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={onPress}
      pressedScale={0.99}
      style={[styles.row, divider && styles.divider]}
    >
      <View style={[styles.iconWell, destructive && styles.destructiveIcon]}>
        <Icon source={icon} size={21} color={tint} />
      </View>
      <View style={styles.copy}>
        <Text style={[styles.rowTitle, destructive && styles.destructiveText]}>{label}</Text>
        {detail ? <Text style={styles.detail}>{detail}</Text> : null}
      </View>
      {!destructive ? (
        <Icon
          source={isRtl ? 'chevron-left' : 'chevron-right'}
          size={20}
          color={colors.textMuted}
        />
      ) : null}
    </TactilePressable>
  );
}

export default function MoreScreen() {
  const router = useRouter();
  const { t, isRtl } = useI18n();
  const { isAuthenticated, isLoading, logout, profile } = useCitizenAuth();
  if (isLoading) {
    return (
      <SafeAreaView style={styles.safeArea} edges={['top', 'left', 'right']}>
        <View style={styles.loading} testID="more-auth-loading">
          <ActivityIndicator color={colors.brand} />
          <Text style={styles.detail}>{t('auth.checkingSession')}</Text>
        </View>
      </SafeAreaView>
    );
  }
  if (!isAuthenticated) return <Redirect href={buildLoginHref('/more') as Href} />;

  const initials =
    profile?.fullName
      ?.trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0])
      .join('')
      .toUpperCase() || 'BG';

  const finishLogout = async (retainReportDraft: boolean) => {
    await logout({ retainReportDraft });
    router.replace('/' as Href);
  };

  const handleLogout = () => {
    void (async () => {
      const draft = profile?.userId ? await loadReportDraft(profile.userId) : null;
      if (!draft || !draftHasRestorableContent(draft)) {
        await finishLogout(false);
        return;
      }
      Alert.alert(t('more.signOutTitle'), t('more.signOutBody'), [
        { text: t('common.cancel'), style: 'cancel' },
        {
          text: t('more.keepDraft'),
          onPress: () => void finishLogout(true),
        },
        {
          text: t('more.clearDraft'),
          style: 'destructive',
          onPress: () => void finishLogout(false),
        },
      ]);
    })();
  };

  return (
    <SafeAreaView style={styles.safeArea} edges={['top', 'left', 'right']}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <Text style={styles.title} accessibilityRole="header">
          {t('more.title')}
        </Text>

        <TactilePressable
          onPress={() => router.push('/profile' as Href)}
          accessibilityRole="button"
          style={styles.profileCard}
        >
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{initials}</Text>
          </View>
          <View style={styles.profileCopy}>
            <Text style={styles.profileName}>{profile?.fullName || t('more.yourProfile')}</Text>
            <Text style={styles.phone}>{profile?.phone || t('more.manageAccount')}</Text>
          </View>
          <Icon
            source={isRtl ? 'chevron-left' : 'chevron-right'}
            size={22}
            color={colors.textMuted}
          />
        </TactilePressable>

        <View style={styles.section}>
          <Text style={styles.sectionLabel}>{t('more.account')}</Text>
          <View style={styles.group}>
            <MenuRow
              icon="account-outline"
              label={t('more.profileNotifications')}
              onPress={() => router.push('/profile' as Href)}
            />
            <MenuRow
              divider
              icon="trophy-outline"
              label={t('more.rewards')}
              onPress={() => router.push('/rewards' as Href)}
            />
            <MenuRow
              divider
              icon="podium"
              label={t('more.leaderboard')}
              onPress={() => router.push('/leaderboard' as Href)}
            />
            <MenuRow
              divider
              icon="shield-check-outline"
              label={t('more.privacy')}
              detail={t('more.privacyDetail')}
              onPress={() => router.push('/privacy' as Href)}
            />
            <MenuRow
              divider
              icon="file-document-outline"
              label={t('legal.termsTitle')}
              onPress={() => router.push('/terms' as Href)}
            />
            <MenuRow
              divider
              icon="clipboard-check-outline"
              label={t('legal.acceptableUseTitle')}
              onPress={() => router.push('/acceptable-use' as Href)}
            />
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionLabel}>{t('more.reports')}</Text>
          <View style={styles.group}>
            <MenuRow
              icon="barcode-scan"
              label={t('more.trackCode')}
              onPress={() => router.push('/track' as Href)}
            />
            <MenuRow
              divider
              icon="map-outline"
              label={t('more.communityMap')}
              onPress={() => router.push('/explore' as Href)}
            />
          </View>
        </View>

        <View style={styles.group}>
          <MenuRow
            testID="logout-button"
            icon="logout"
            label={t('common.signOut')}
            destructive
            onPress={handleLogout}
          />
        </View>

        <View style={styles.section}>
          <LanguageSwitcher />
        </View>

        <Text style={styles.version}>{t('more.version')}</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.background },
  loading: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing[3],
    padding: spacing[5],
  },
  scroll: {
    paddingHorizontal: spacing[5],
    paddingTop: spacing[3],
    paddingBottom: 110,
    gap: spacing[6],
  },
  title: {
    fontSize: 34,
    lineHeight: 40,
    fontWeight: '800',
    letterSpacing: -1.1,
    color: colors.text,
  },
  profileCard: {
    minHeight: 82,
    padding: spacing[4],
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing[3],
    borderRadius: radii.lg,
    backgroundColor: colors.surface,
  },
  avatar: {
    width: 50,
    height: 50,
    borderRadius: 17,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.brand,
  },
  avatarText: { fontSize: 17, fontWeight: '700', color: colors.textInverse },
  profileCopy: { flex: 1, gap: 2 },
  profileName: { fontSize: 17, fontWeight: '700', letterSpacing: -0.25, color: colors.text },
  phone: { fontSize: 13, color: colors.textMuted },
  section: { gap: spacing[2] },
  sectionLabel: {
    marginStart: spacing[4],
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 0.75,
    color: colors.textMuted,
  },
  group: {
    overflow: 'hidden',
    paddingHorizontal: spacing[4],
    borderRadius: radii.lg,
    backgroundColor: colors.surface,
  },
  row: { minHeight: 66, flexDirection: 'row', alignItems: 'center', gap: spacing[3] },
  divider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  iconWell: {
    width: 34,
    height: 34,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.brandSoft,
  },
  destructiveIcon: { backgroundColor: colors.dangerSoft },
  copy: { flex: 1 },
  rowTitle: { fontSize: 15, fontWeight: '600', color: colors.text },
  destructiveText: { color: colors.danger },
  detail: { marginTop: 2, fontSize: 12, color: colors.textMuted },
  version: { textAlign: 'center', fontSize: 12, color: colors.textMuted },
});

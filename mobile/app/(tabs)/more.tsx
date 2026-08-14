import { Alert, ScrollView, StyleSheet, View } from 'react-native';
import { Icon, Text } from 'react-native-paper';
import { Redirect, useRouter, type Href } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useCitizenAuth } from '@/auth';
import { buildLoginHref } from '@/auth/returnTo';
import { TactilePressable } from '@/components/TactilePressable';
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
      {!destructive ? <Icon source="chevron-right" size={20} color={colors.textMuted} /> : null}
    </TactilePressable>
  );
}

export default function MoreScreen() {
  const router = useRouter();
  const { isAuthenticated, isLoading, logout, profile } = useCitizenAuth();
  if (isLoading) return null;
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
      Alert.alert(
        'Sign out?',
        'Clear your in-progress report draft on this device, or keep it for the next time you sign in with this account.',
        [
          { text: 'Cancel', style: 'cancel' },
          {
            text: 'Keep draft & sign out',
            onPress: () => void finishLogout(true),
          },
          {
            text: 'Clear draft & sign out',
            style: 'destructive',
            onPress: () => void finishLogout(false),
          },
        ],
      );
    })();
  };

  return (
    <SafeAreaView style={styles.safeArea} edges={['top', 'left', 'right']}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <Text style={styles.title} accessibilityRole="header">
          More
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
            <Text style={styles.profileName}>{profile?.fullName || 'Your profile'}</Text>
            <Text style={styles.phone}>{profile?.phone || 'Manage your account'}</Text>
          </View>
          <Icon source="chevron-right" size={22} color={colors.textMuted} />
        </TactilePressable>

        <View style={styles.section}>
          <Text style={styles.sectionLabel}>ACCOUNT</Text>
          <View style={styles.group}>
            <MenuRow
              icon="account-outline"
              label="Profile and notifications"
              onPress={() => router.push('/profile' as Href)}
            />
            <MenuRow
              divider
              icon="shield-check-outline"
              label="Privacy"
              detail="How your information is protected"
              onPress={() => router.push('/privacy' as Href)}
            />
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionLabel}>REPORTS</Text>
          <View style={styles.group}>
            <MenuRow
              icon="barcode-scan"
              label="Track with a code"
              onPress={() => router.push('/track' as Href)}
            />
            <MenuRow
              divider
              icon="map-outline"
              label="Community map"
              onPress={() => router.push('/explore' as Href)}
            />
          </View>
        </View>

        <View style={styles.group}>
          <MenuRow
            testID="logout-button"
            icon="logout"
            label="Sign out"
            destructive
            onPress={handleLogout}
          />
        </View>

        <Text style={styles.version}>BaladiGuard · Citizen services</Text>
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
    marginLeft: spacing[4],
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

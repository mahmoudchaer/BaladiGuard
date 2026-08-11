import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { Icon, Text } from 'react-native-paper';
import { Redirect, useRouter, type Href } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useCitizenAuth } from '@/auth';
import { buildLoginHref } from '@/auth/returnTo';
import { AppBottomNavigation } from '@/components/AppBottomNavigation';
import { colors, radii, spacing, touchTargetMin } from '@/theme';

export default function MoreScreen() {
  const router = useRouter();
  const { isAuthenticated, isLoading, logout, profile } = useCitizenAuth();
  if (isLoading) return null;
  if (!isAuthenticated) return <Redirect href={buildLoginHref('/more') as Href} />;
  const rows = [
    {
      label: 'Profile',
      detail: profile?.phone ?? 'Account details',
      icon: 'account-outline',
      href: '/profile',
    },
    {
      label: 'Privacy notice',
      detail: 'How we protect citizen information',
      icon: 'shield-lock-outline',
      href: '/privacy',
    },
  ];
  return (
    <SafeAreaView style={styles.safeArea} edges={['top', 'left', 'right']}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View>
          <Text style={styles.title} accessibilityRole="header">
            More
          </Text>
          <Text style={styles.subtitle}>Account and trusted information</Text>
        </View>
        <View style={styles.card}>
          {rows.map((row, index) => (
            <Pressable
              key={row.label}
              onPress={() => router.push(row.href as Href)}
              accessibilityRole="button"
              style={({ pressed }) => [
                styles.row,
                index > 0 && styles.divider,
                pressed && styles.pressed,
              ]}
            >
              <Icon source={row.icon} size={24} color={colors.brandDark} />
              <View style={styles.copy}>
                <Text style={styles.rowTitle}>{row.label}</Text>
                <Text style={styles.detail}>{row.detail}</Text>
              </View>
              <Icon source="chevron-right" size={22} color={colors.textMuted} />
            </Pressable>
          ))}
        </View>
        <Pressable
          testID="logout-button"
          accessibilityRole="button"
          onPress={async () => {
            await logout();
            router.replace('/' as Href);
          }}
          style={({ pressed }) => [styles.signOut, pressed && styles.pressed]}
        >
          <Icon source="logout" size={22} color={colors.danger} />
          <Text style={styles.signOutText}>Sign out</Text>
        </Pressable>
      </ScrollView>
      <AppBottomNavigation active="more" />
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.background },
  scroll: { padding: spacing[5], gap: spacing[5] },
  title: { fontSize: 28, fontWeight: '800', color: colors.text },
  subtitle: { marginTop: spacing[1], fontSize: 15, color: colors.textSecondary },
  card: {
    overflow: 'hidden',
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  row: {
    minHeight: 72,
    paddingHorizontal: spacing[4],
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing[3],
  },
  divider: { borderTopWidth: 1, borderTopColor: colors.border },
  pressed: { backgroundColor: colors.surfaceSubtle },
  copy: { flex: 1 },
  rowTitle: { fontSize: 16, fontWeight: '700', color: colors.text },
  detail: { marginTop: 2, fontSize: 13, color: colors.textSecondary },
  signOut: {
    minHeight: touchTargetMin,
    padding: spacing[4],
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing[2],
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  signOutText: { fontWeight: '700', color: colors.danger },
});

/**
 * Landing surface for notification deep links `/t/{trackingCode}` (issue #257).
 *
 * - Malformed codes → safe fallback (no ownership language).
 * - Logged out → track (possession) or sign-in with returnTo.
 * - Logged in → citizen-safe track lookup for the code.
 * Invalid / inaccessible outcomes use track-form error text only (no “not yours”).
 */

import { useEffect } from 'react';
import { useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { Banner, Button, Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useCitizenAuth } from '@/auth';
import { buildLoginHref } from '@/auth/returnTo';
import { colors, spacing, typography } from '@/theme';
import { isValidTrackingCode, normalizeTrackingCode } from '@/utils/trackingCode';

function paramToString(value: string | string[] | undefined): string {
  if (Array.isArray(value)) {
    return value[0] ?? '';
  }
  return value ?? '';
}

export default function NotificationTicketDeepLinkScreen() {
  const router = useRouter();
  const { code } = useLocalSearchParams<{ code?: string | string[] }>();
  const rawCode = paramToString(code);
  const normalized = normalizeTrackingCode(rawCode);
  const valid = isValidTrackingCode(normalized);
  const { isAuthenticated, isLoading } = useCitizenAuth();
  const trackHref = valid
    ? (`/track?trackingCode=${encodeURIComponent(normalized)}` as Href)
    : ('/track' as Href);

  useEffect(() => {
    if (isLoading || !valid || !isAuthenticated) {
      return;
    }
    router.replace(trackHref);
  }, [isLoading, valid, isAuthenticated, trackHref, router]);

  if (isLoading || (valid && isAuthenticated)) {
    return (
      <SafeAreaView style={styles.safeArea} edges={['bottom']}>
        <View style={styles.centered} accessibilityLabel="Opening report">
          <ActivityIndicator color={colors.brand} />
          {valid ? <Text style={styles.openingHint}>Opening report status…</Text> : null}
        </View>
      </SafeAreaView>
    );
  }

  if (!valid) {
    return (
      <SafeAreaView style={styles.safeArea} edges={['bottom']}>
        <View style={styles.container}>
          <Text variant="titleLarge" style={styles.title}>
            Link cannot be used
          </Text>
          <Text style={styles.body}>
            This link is missing a valid tracking code. You can still look up a report with a code
            from your receipt or SMS, or return home.
          </Text>
          <Button
            mode="contained"
            onPress={() => router.replace('/track' as Href)}
            style={styles.button}
            accessibilityLabel="Track a report"
          >
            Track a report
          </Button>
          <Button mode="outlined" onPress={() => router.replace('/' as Href)} style={styles.button}>
            Home
          </Button>
        </View>
      </SafeAreaView>
    );
  }

  const deepPath = `/t/${normalized}`;

  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom']}>
      <View style={styles.container}>
        <Text variant="titleLarge" style={styles.title}>
          Continue with this report
        </Text>
        <Banner visible icon="information-outline" style={styles.banner}>
          Sign in is optional. Tracking only needs a valid code from your notification. Status is
          shared when the code is valid—same as the track screen.
        </Banner>
        <Text style={styles.body}>
          Tracking code from the link: {normalized}. Choose how to continue.
        </Text>
        <Button
          mode="contained"
          onPress={() => router.replace(trackHref)}
          style={styles.button}
          accessibilityLabel="Track with this code"
        >
          Track with this code
        </Button>
        <Button
          mode="outlined"
          onPress={() => router.push(buildLoginHref(deepPath) as Href)}
          style={styles.button}
          accessibilityLabel="Sign in to continue"
        >
          Sign in
        </Button>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background,
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing[3],
    padding: spacing[5],
  },
  openingHint: {
    color: colors.textSecondary,
  },
  container: {
    flex: 1,
    padding: spacing[5],
    gap: spacing[3],
  },
  title: {
    color: colors.brandDark,
    fontWeight: '700',
    fontSize: typography.sectionTitle,
  },
  body: {
    color: colors.textSecondary,
    lineHeight: 22,
  },
  button: {
    alignSelf: 'stretch',
  },
  banner: {
    backgroundColor: colors.surface,
  },
});

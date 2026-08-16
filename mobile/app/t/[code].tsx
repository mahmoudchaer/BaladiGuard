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
import { useI18n } from '@/i18n/LocaleProvider';
import { colors, spacing, typography } from '@/theme';
import { isValidTrackingCode, normalizeTrackingCode } from '@/utils/trackingCode';

function paramToString(value: string | string[] | undefined): string {
  if (Array.isArray(value)) {
    return value[0] ?? '';
  }
  return value ?? '';
}

export default function NotificationTicketDeepLinkScreen() {
  const { t } = useI18n();
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
        <View style={styles.centered} accessibilityLabel={t('track.openingA11y')}>
          <ActivityIndicator color={colors.brand} />
          {valid ? <Text style={styles.openingHint}>{t('track.opening')}</Text> : null}
        </View>
      </SafeAreaView>
    );
  }

  if (!valid) {
    return (
      <SafeAreaView style={styles.safeArea} edges={['bottom']}>
        <View style={styles.container}>
          <Text variant="titleLarge" style={styles.title}>
            {t('track.invalidTitle')}
          </Text>
          <Text style={styles.body}>{t('track.invalidBody')}</Text>
          <Button
            mode="contained"
            onPress={() => router.replace('/track' as Href)}
            style={styles.button}
            accessibilityLabel={t('track.title')}
          >
            {t('track.title')}
          </Button>
          <Button mode="outlined" onPress={() => router.replace('/' as Href)} style={styles.button}>
            {t('tabs.home')}
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
          {t('track.continueTitle')}
        </Text>
        <Banner visible icon="information-outline" style={styles.banner}>
          {t('track.optionalSignIn')}
        </Banner>
        <Text style={styles.body}>{t('track.codeFromLink', { code: normalized })}</Text>
        <Button
          mode="contained"
          onPress={() => router.replace(trackHref)}
          style={styles.button}
          accessibilityLabel={t('track.trackWithCode')}
        >
          {t('track.trackWithCode')}
        </Button>
        <Button
          mode="outlined"
          onPress={() => router.push(buildLoginHref(deepPath) as Href)}
          style={styles.button}
          accessibilityLabel={t('track.signInToContinue')}
        >
          {t('common.signIn')}
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

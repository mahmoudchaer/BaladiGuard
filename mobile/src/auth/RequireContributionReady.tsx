import { useState } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { Button, Text } from 'react-native-paper';
import { Link, Redirect, type Href } from 'expo-router';

import { useCitizenAuth } from '@/auth';
import { buildLoginHref } from '@/auth/returnTo';
import { useI18n } from '@/i18n/LocaleProvider';
import { acceptCitizenLegal } from '@/services/api/citizenAuth';
import { colors, spacing } from '@/theme';

type RequireContributionReadyProps = {
  children: React.ReactNode;
  returnTo: string;
};

/**
 * Gates contribution entry points on a verified-phone citizen session (#270).
 * Guests are redirected to phone OTP login. Inactive or not-ready sessions stay
 * on an explicit blocked screen so they are not bounced into a login loop.
 */
export function RequireContributionReady({ children, returnTo }: RequireContributionReadyProps) {
  const { t, locale } = useI18n();
  const {
    isLoading,
    isAuthenticated,
    contributionReady,
    profile,
    accessToken,
    refreshProfile,
    logout,
  } = useCitizenAuth();
  const [legalBusy, setLegalBusy] = useState(false);
  const [legalError, setLegalError] = useState<string | null>(null);

  if (isLoading) {
    return (
      <View style={styles.loading} testID="auth-loading">
        <ActivityIndicator />
        <Text variant="bodyMedium" style={styles.loadingText}>
          {t('auth.checkingSession')}
        </Text>
      </View>
    );
  }

  if (!isAuthenticated) {
    return <Redirect href={buildLoginHref(returnTo) as Href} />;
  }

  if (!contributionReady) {
    return (
      <View style={styles.gate} testID="account-blocked">
        <Text variant="titleMedium" style={styles.title}>
          {t('auth.accountBlockedTitle')}
        </Text>
        <Text variant="bodyMedium" style={styles.loadingText}>
          {t('auth.accountBlockedBody')}
        </Text>
        <Button mode="contained" onPress={() => void logout()} testID="account-blocked-sign-out">
          {t('common.signOut')}
        </Button>
      </View>
    );
  }

  if (profile?.legalAcceptanceRequired) {
    return (
      <View style={styles.gate} testID="legal-acceptance-gate">
        <Text variant="titleMedium" style={styles.title}>
          {t('profile.legalRequiredBanner')}
        </Text>
        <Link href={'/terms' as Href} asChild>
          <Button mode="text" textColor={colors.brandDark}>
            {t('legal.termsTitle')}
          </Button>
        </Link>
        <Link href={'/privacy' as Href} asChild>
          <Button mode="text" textColor={colors.brandDark}>
            {t('legal.privacyTitle')}
          </Button>
        </Link>
        <Link href={'/acceptable-use' as Href} asChild>
          <Button mode="text" textColor={colors.brandDark}>
            {t('legal.acceptableUseTitle')}
          </Button>
        </Link>
        {legalError ? (
          <Text variant="bodyMedium" style={styles.error} accessibilityRole="alert">
            {legalError}
          </Text>
        ) : null}
        <Button
          mode="contained"
          loading={legalBusy}
          disabled={legalBusy || !accessToken}
          testID="accept-legal-gate"
          onPress={() => {
            void (async () => {
              if (!accessToken) return;
              setLegalBusy(true);
              setLegalError(null);
              try {
                await acceptCitizenLegal(accessToken, { acceptLegal: true, locale });
                await refreshProfile();
              } catch (error) {
                setLegalError(error instanceof Error ? error.message : t('profile.legalAcceptFailed'));
              } finally {
                setLegalBusy(false);
              }
            })();
          }}
        >
          {t('profile.acceptLegal')}
        </Button>
      </View>
    );
  }

  return children;
}

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 12,
    padding: 24,
    backgroundColor: '#FFFFFF',
  },
  loadingText: {
    color: '#64748B',
  },
  gate: {
    flex: 1,
    justifyContent: 'center',
    gap: spacing[3],
    padding: spacing[5],
    backgroundColor: colors.background,
  },
  title: {
    fontWeight: '700',
    color: colors.text,
  },
  error: {
    color: colors.danger,
  },
});

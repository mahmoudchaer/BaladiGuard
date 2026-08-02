import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { Redirect, type Href } from 'expo-router';

import { useCitizenAuth } from '@/auth';
import { buildLoginHref } from '@/auth/returnTo';

type RequireContributionReadyProps = {
  children: React.ReactNode;
  returnTo: string;
};

/**
 * Gates contribution entry points on a contribution-ready citizen session.
 * Guests and incomplete profiles are redirected to phone OTP login.
 */
export function RequireContributionReady({ children, returnTo }: RequireContributionReadyProps) {
  const { isLoading, contributionReady } = useCitizenAuth();

  if (isLoading) {
    return (
      <View style={styles.loading} testID="auth-loading">
        <ActivityIndicator />
        <Text variant="bodyMedium" style={styles.loadingText}>
          Checking your session…
        </Text>
      </View>
    );
  }

  if (!contributionReady) {
    return <Redirect href={buildLoginHref(returnTo) as Href} />;
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
});

import { Pressable, StyleSheet } from 'react-native';
import { Stack, useRouter, type Href } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Icon, PaperProvider, Text } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { CitizenAuthProvider } from '@/auth';
import { colors, theme, typography } from '@/theme';

function ReliableBackButton() {
  const router = useRouter();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="Go back"
      hitSlop={10}
      onPress={() => {
        if (router.canGoBack()) {
          router.back();
        } else {
          router.replace('/' as Href);
        }
      }}
      style={({ pressed }) => [styles.backButton, pressed && styles.backButtonPressed]}
    >
      <Icon source="chevron-left" size={25} color={colors.brandDark} />
      <Text style={styles.backLabel}>Back</Text>
    </Pressable>
  );
}

/**
 * Notification deep links (#257): route `t/[code]` handles HTTPS Universal /
 * App Links and `baladiguard://t/{code}` once the OS opens the app. Native host
 * claiming is configured in `mobile/app.config.ts` (associatedDomains + intentFilters).
 */
export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <PaperProvider theme={theme}>
        <CitizenAuthProvider>
          <StatusBar style="dark" />
          <Stack
            screenOptions={{
              headerStyle: { backgroundColor: colors.surface },
              headerTintColor: colors.brandDark,
              headerTitleStyle: { fontWeight: '700', fontSize: typography.sectionTitle },
              headerShadowVisible: false,
              headerBackVisible: false,
              headerLeft: () => <ReliableBackButton />,
              contentStyle: { backgroundColor: colors.background },
            }}
          >
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen name="report/index" options={{ title: 'New report' }} />
            <Stack.Screen name="track/index" options={{ title: 'Track a report' }} />
            <Stack.Screen name="t/[code]" options={{ title: 'Report link' }} />
            <Stack.Screen name="login/index" options={{ title: 'Sign in' }} />
            <Stack.Screen name="profile/index" options={{ title: 'Profile' }} />
            <Stack.Screen name="privacy/index" options={{ title: 'Privacy notice' }} />
            <Stack.Screen name="public/[ticketNumber]" options={{ title: 'Public report' }} />
          </Stack>
        </CitizenAuthProvider>
      </PaperProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  backButton: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    marginLeft: -8,
    paddingHorizontal: 4,
  },
  backButtonPressed: { opacity: 0.55 },
  backLabel: { marginLeft: -2, fontSize: 16, fontWeight: '500', color: colors.brandDark },
});

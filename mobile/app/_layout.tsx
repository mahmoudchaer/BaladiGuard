import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { PaperProvider } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { CitizenAuthProvider } from '@/auth';
import { colors, theme, typography } from '@/theme';

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
              headerBackTitle: 'Home',
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

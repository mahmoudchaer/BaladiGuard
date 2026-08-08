import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { PaperProvider } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { CitizenAuthProvider } from '@/auth';
import { colors, theme, typography } from '@/theme';

/**
 * Navigation decision (issue #52): keep a Stack, not bottom tabs.
 * The citizen app is a small, task-first flow (report / track / history / profile)
 * that fans out from a single home hub — tabs would add persistent chrome without
 * meaningfully improving discoverability, and would demote "Report an issue" (the
 * primary action) to a tab among equals instead of the prominent CTA it is on home.
 * We improve discoverability instead via clear home CTAs, themed headers, and
 * consistent back-navigation. `history/index` is registered below so signed-in
 * citizens get a titled header + back action when opened from home or the profile.
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
            <Stack.Screen name="index" options={{ headerShown: false }} />
            <Stack.Screen name="report/index" options={{ title: 'New report' }} />
            <Stack.Screen name="track/index" options={{ title: 'Track a report' }} />
            <Stack.Screen name="history/index" options={{ title: 'Report history' }} />
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

import { Stack } from 'expo-router';
import { PaperProvider } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { CitizenAuthProvider } from '@/auth';
import { theme } from '@/theme';

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <PaperProvider theme={theme}>
        <CitizenAuthProvider>
          <Stack>
            <Stack.Screen name="index" options={{ headerShown: false }} />
            <Stack.Screen
              name="report/index"
              options={{
                title: 'New report',
                headerBackTitle: 'Home',
              }}
            />
            <Stack.Screen
              name="track/index"
              options={{
                title: 'Track a report',
                headerBackTitle: 'Home',
              }}
            />
            <Stack.Screen
              name="login/index"
              options={{
                title: 'Sign in',
                headerBackTitle: 'Home',
              }}
            />
          </Stack>
        </CitizenAuthProvider>
      </PaperProvider>
    </SafeAreaProvider>
  );
}

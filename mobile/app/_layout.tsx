import { Pressable, StyleSheet } from 'react-native';
import { Stack, useRouter, type Href } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Icon, PaperProvider, Text } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { CitizenAuthProvider } from '@/auth';
import { LocaleProvider, useI18n } from '@/i18n/LocaleProvider';
import { colors, theme, typography } from '@/theme';

function ReliableBackButton() {
  const router = useRouter();
  const { t, isRtl } = useI18n();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={t('a11y.goBack')}
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
      <Icon source={isRtl ? 'chevron-right' : 'chevron-left'} size={25} color={colors.brandDark} />
      <Text style={styles.backLabel}>{t('common.back')}</Text>
    </Pressable>
  );
}

/**
 * Notification deep links (#257): route `t/[code]` handles HTTPS Universal /
 * App Links and `baladiguard://t/{code}` once the OS opens the app. Native host
 * claiming is configured in `mobile/app.config.ts` (associatedDomains + intentFilters).
 */
function LocalizedStack() {
  const { t } = useI18n();
  return (
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
      <Stack.Screen name="report/index" options={{ title: t('screens.newReport') }} />
      <Stack.Screen name="track/index" options={{ title: t('screens.track') }} />
      <Stack.Screen name="t/[code]" options={{ title: t('screens.reportLink') }} />
      <Stack.Screen name="login/index" options={{ title: t('screens.signIn') }} />
      <Stack.Screen name="profile/index" options={{ title: t('screens.profile') }} />
      <Stack.Screen name="privacy/index" options={{ title: t('screens.privacy') }} />
      <Stack.Screen name="terms/index" options={{ title: t('screens.terms') }} />
      <Stack.Screen name="acceptable-use/index" options={{ title: t('screens.acceptableUse') }} />
      <Stack.Screen name="public/[ticketNumber]" options={{ title: t('screens.publicReport') }} />
    </Stack>
  );
}

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <PaperProvider theme={theme}>
        <LocaleProvider>
          <CitizenAuthProvider>
            <StatusBar style="dark" />
            <LocalizedStack />
          </CitizenAuthProvider>
        </LocaleProvider>
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

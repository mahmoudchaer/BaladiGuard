import { ScrollView, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaView } from 'react-native-safe-area-context';

import { colors, spacing } from '@/theme';

/**
 * Citizen-facing privacy notice (issue #190).
 * Ships independently of the OTP auth stack; full policy in docs/privacy-lifecycle.md.
 * No BrandMark here — this screen has no brand header context.
 */
export default function PrivacyNoticeScreen() {
  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={styles.content}>
        <Text variant="headlineSmall" style={styles.title}>
          Privacy notice
        </Text>
        <Text variant="bodyMedium" style={styles.paragraph}>
          BaladiGuard collects the minimum information needed to accept, route, and resolve
          municipal infrastructure reports.
        </Text>

        <Text variant="titleMedium" style={styles.section}>
          What we collect
        </Text>
        <Text variant="bodyMedium" style={styles.paragraph}>
          Verified phone number for login and ownership; optional name and email; notification
          preferences; and report details (description, location, and photo). Each report keeps an
          immutable contact snapshot for municipal follow-up.
        </Text>

        <Text variant="titleMedium" style={styles.section}>
          Your controls
        </Text>
        <Text variant="bodyMedium" style={styles.paragraph}>
          You can update your profile, export your account data, and delete your account. Deletion
          anonymizes your profile while municipal ticket records needed for operations remain.
        </Text>

        <Text variant="titleMedium" style={styles.section}>
          What we do not do
        </Text>
        <Text variant="bodyMedium" style={styles.paragraph}>
          We do not use citizen passwords, sell personal data, or put real citizen information into
          test fixtures or demo seeds.
        </Text>

        <View style={styles.footnoteBox}>
          <Text variant="bodySmall" style={styles.footnote}>
            Full retention periods, deletion behavior, and privacy request handling are documented
            in the BaladiGuard privacy lifecycle policy.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing[5],
    gap: spacing[3],
    paddingBottom: spacing[8],
  },
  title: {
    fontWeight: '700',
    color: colors.brandDark,
    marginBottom: spacing[1],
  },
  section: {
    marginTop: spacing[2],
    fontWeight: '600',
    color: colors.text,
  },
  paragraph: {
    color: colors.textSecondary,
    lineHeight: 22,
  },
  footnoteBox: {
    marginTop: spacing[4],
    paddingTop: spacing[3],
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  footnote: {
    color: colors.textMuted,
    lineHeight: 18,
  },
});

import { ScrollView, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaView } from 'react-native-safe-area-context';

/**
 * Citizen-facing privacy notice (issue #190).
 * Ships independently of the OTP auth stack; full policy in docs/privacy-lifecycle.md.
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
    backgroundColor: '#FFFFFF',
  },
  content: {
    padding: 24,
    gap: 12,
    paddingBottom: 40,
  },
  title: {
    fontWeight: '700',
    color: '#0B5FFF',
    marginBottom: 4,
  },
  section: {
    marginTop: 8,
    fontWeight: '600',
    color: '#0F172A',
  },
  paragraph: {
    color: '#475569',
    lineHeight: 22,
  },
  footnoteBox: {
    marginTop: 16,
    paddingTop: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: '#CBD5E1',
  },
  footnote: {
    color: '#64748B',
    lineHeight: 18,
  },
});

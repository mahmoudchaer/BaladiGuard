import { StyleSheet, View } from 'react-native';
import { Button, Text } from 'react-native-paper';

import type { CitizenProfile } from '@/types/citizen';

type ProfileSummaryProps = {
  profile: CitizenProfile;
  onEdit: () => void;
  onChangePhone: () => void;
  onLogout: () => void;
  isLoggingOut?: boolean;
};

function formatPreference(profile: CitizenProfile): string {
  const { ticketUpdates, announcements } = profile.notificationPreferences;
  const parts = [`Ticket updates: ${ticketUpdates}`];
  parts.push(announcements ? 'Announcements: on' : 'Announcements: off');
  return parts.join(' · ');
}

export function ProfileSummary({
  profile,
  onEdit,
  onChangePhone,
  onLogout,
  isLoggingOut = false,
}: ProfileSummaryProps) {
  const accountStatus = !profile.active
    ? 'Inactive'
    : profile.contributionReady
      ? 'Contribution-ready'
      : 'Setup incomplete';

  return (
    <View style={styles.container} testID="profile-summary">
      <Text variant="titleLarge" style={styles.title}>
        Your profile
      </Text>
      <Text variant="bodyMedium" style={styles.subtitle}>
        Review your identity, communication preferences, and public attribution settings.
      </Text>

      <View style={styles.row}>
        <Text variant="labelLarge" style={styles.label}>
          Full name
        </Text>
        <Text variant="bodyLarge" testID="profile-full-name">
          {profile.fullName?.trim() || 'Not set'}
        </Text>
      </View>

      <View style={styles.row}>
        <Text variant="labelLarge" style={styles.label}>
          Verified phone
        </Text>
        <Text variant="bodyLarge" testID="profile-phone">
          {profile.phone}
        </Text>
        <Text variant="bodySmall" style={styles.hint}>
          Verified {new Date(profile.phoneVerifiedAt).toLocaleString()}
        </Text>
      </View>

      <View style={styles.row}>
        <Text variant="labelLarge" style={styles.label}>
          Email (optional)
        </Text>
        <Text variant="bodyLarge" testID="profile-email">
          {profile.email ?? 'Not set'}
        </Text>
        <Text variant="bodySmall" style={styles.hint}>
          Optional for notifications only — not used to sign in or recover your phone.
        </Text>
      </View>

      <View style={styles.row}>
        <Text variant="labelLarge" style={styles.label}>
          Notification preferences
        </Text>
        <Text variant="bodyLarge" testID="profile-notifications">
          {formatPreference(profile)}
        </Text>
      </View>

      <View style={styles.row}>
        <Text variant="labelLarge" style={styles.label}>
          Public name visibility
        </Text>
        <Text variant="bodyLarge" testID="profile-public-name">
          {profile.publicNameVisible ? 'Visible on owned reports' : 'Hidden (Anonymous)'}
        </Text>
        <Text variant="bodySmall" style={styles.hint}>
          Defaults off. Changes apply dynamically to existing and future owned reports.
        </Text>
      </View>

      <View style={styles.row}>
        <Text variant="labelLarge" style={styles.label}>
          Account / session status
        </Text>
        <Text variant="bodyLarge" testID="profile-status">
          {`${accountStatus}${profile.active ? ' · Signed in' : ''}`}
        </Text>
      </View>

      <Button mode="contained" onPress={onEdit} style={styles.button} testID="edit-profile-button">
        Edit profile
      </Button>
      <Button
        mode="outlined"
        onPress={onChangePhone}
        style={styles.button}
        testID="change-phone-button"
      >
        Change phone number
      </Button>
      <Button
        mode="text"
        onPress={onLogout}
        loading={isLoggingOut}
        disabled={isLoggingOut}
        style={styles.button}
        testID="profile-logout-button"
      >
        Sign out
      </Button>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: 14,
  },
  title: {
    fontWeight: '700',
  },
  subtitle: {
    color: '#475569',
    marginBottom: 4,
  },
  row: {
    gap: 2,
  },
  label: {
    color: '#64748B',
  },
  hint: {
    color: '#64748B',
  },
  button: {
    alignSelf: 'flex-start',
  },
});

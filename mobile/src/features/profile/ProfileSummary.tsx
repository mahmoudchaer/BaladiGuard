import { StyleSheet, View } from 'react-native';
import { Button, Text } from 'react-native-paper';
import { Link, type Href } from 'expo-router';

import { colors, radii, spacing, touchTargetMin, typography } from '@/theme';
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

type SettingsRowProps = {
  label: string;
  value: string;
  hint?: string;
  valueTestID?: string;
};

function SettingsRow({ label, value, hint, valueTestID }: SettingsRowProps) {
  return (
    <View style={styles.row}>
      <Text variant="labelLarge" style={styles.rowLabel}>
        {label}
      </Text>
      <Text variant="bodyLarge" style={styles.rowValue} testID={valueTestID}>
        {value}
      </Text>
      {hint ? (
        <Text variant="bodySmall" style={styles.rowHint}>
          {hint}
        </Text>
      ) : null}
    </View>
  );
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
      : 'Not contribution-ready';

  return (
    <View style={styles.container} testID="profile-summary">
      <View style={styles.header}>
        <Text variant="titleLarge" style={styles.title}>
          Your profile
        </Text>
        <Text variant="bodyMedium" style={styles.subtitle}>
          Review your identity, communication preferences, and public attribution settings. Full
          name is optional — a verified phone is enough to submit reports.
        </Text>
      </View>

      <View style={styles.section}>
        <Text variant="labelLarge" style={styles.sectionTitle}>
          Account
        </Text>
        <View style={styles.card}>
          <SettingsRow
            label="Full name (optional)"
            value={profile.fullName?.trim() || 'Not set'}
            hint="Optional. Not used for sign-in, recovery, ownership, or reporting."
            valueTestID="profile-full-name"
          />
          <View style={styles.divider} />
          <SettingsRow
            label="Verified phone"
            value={profile.phone}
            hint={`Verified ${new Date(profile.phoneVerifiedAt).toLocaleString()}`}
            valueTestID="profile-phone"
          />
          <View style={styles.divider} />
          <SettingsRow
            label="Email (optional)"
            value={profile.email ?? 'Not set'}
            hint="Optional for notifications only — not used to sign in or recover your phone."
            valueTestID="profile-email"
          />
        </View>
      </View>

      <View style={styles.section}>
        <Text variant="labelLarge" style={styles.sectionTitle}>
          Preferences
        </Text>
        <View style={styles.card}>
          <SettingsRow
            label="Notification preferences"
            value={formatPreference(profile)}
            valueTestID="profile-notifications"
          />
          <View style={styles.divider} />
          <SettingsRow
            label="Public name visibility"
            value={profile.publicNameVisible ? 'Visible on owned reports' : 'Hidden (Anonymous)'}
            hint="Defaults off. Changes apply dynamically to existing and future owned reports."
            valueTestID="profile-public-name"
          />
        </View>
      </View>

      <View style={styles.section}>
        <Text variant="labelLarge" style={styles.sectionTitle}>
          Session
        </Text>
        <View style={styles.card}>
          <SettingsRow
            label="Account / session status"
            value={`${accountStatus}${profile.active ? ' · Signed in' : ''}`}
            valueTestID="profile-status"
          />
        </View>
      </View>

      <View style={styles.actions}>
        <Button
          mode="contained"
          onPress={onEdit}
          style={styles.button}
          contentStyle={styles.controlContent}
          buttonColor={colors.brand}
          textColor={colors.textInverse}
          testID="edit-profile-button"
        >
          Edit profile
        </Button>
        <Button
          mode="outlined"
          onPress={onChangePhone}
          style={styles.button}
          contentStyle={styles.controlContent}
          textColor={colors.brandDark}
          testID="change-phone-button"
        >
          Change phone number
        </Button>
        <Link href={'/privacy' as Href} asChild>
          <Button
            mode="text"
            style={styles.button}
            contentStyle={styles.controlContent}
            textColor={colors.textSecondary}
            icon="shield-account-outline"
          >
            Privacy notice
          </Button>
        </Link>
        <Button
          mode="text"
          onPress={onLogout}
          loading={isLoggingOut}
          disabled={isLoggingOut}
          style={styles.button}
          contentStyle={styles.controlContent}
          textColor={colors.danger}
          testID="profile-logout-button"
        >
          Sign out
        </Button>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing[5],
  },
  header: {
    gap: spacing[1],
  },
  title: {
    fontWeight: '700',
    color: colors.text,
  },
  subtitle: {
    color: colors.textSecondary,
    lineHeight: 20,
  },
  section: {
    gap: spacing[2],
  },
  sectionTitle: {
    color: colors.textMuted,
    fontSize: typography.label,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  card: {
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    overflow: 'hidden',
  },
  divider: {
    height: 1,
    backgroundColor: colors.border,
  },
  row: {
    gap: 2,
    padding: spacing[3],
  },
  rowLabel: {
    color: colors.textMuted,
    fontSize: typography.metadata,
  },
  rowValue: {
    color: colors.text,
  },
  rowHint: {
    color: colors.textMuted,
    marginTop: 2,
  },
  actions: {
    gap: spacing[2],
  },
  button: {
    width: '100%',
    borderRadius: radii.md,
  },
  controlContent: {
    minHeight: touchTargetMin,
  },
});

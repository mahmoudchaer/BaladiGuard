import { StyleSheet, View } from 'react-native';
import { Button, Text } from 'react-native-paper';
import { Link, type Href } from 'expo-router';

import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { useI18n } from '@/i18n/LocaleProvider';
import { colors, radii, spacing, touchTargetMin, typography } from '@/theme';
import type { CitizenProfile } from '@/types/citizen';

type ProfileSummaryProps = {
  profile: CitizenProfile;
  onEdit: () => void;
  onChangePhone: () => void;
  onLogout: () => void;
  isLoggingOut?: boolean;
};

function formatPreference(
  profile: CitizenProfile,
  translate: (key: string, vars?: Record<string, string | number>) => string,
): string {
  const { ticketUpdates, announcements } = profile.notificationPreferences;
  const parts = [translate('profile.ticketUpdates', { value: ticketUpdates })];
  parts.push(
    announcements ? translate('profile.announcementsOn') : translate('profile.announcementsOff'),
  );
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
  const { t, locale } = useI18n();
  const accountStatus = !profile.active
    ? t('profile.inactive')
    : profile.contributionReady
      ? t('profile.contributionReady')
      : t('profile.notContributionReady');

  return (
    <View style={styles.container} testID="profile-summary">
      <View style={styles.header}>
        <Text variant="titleLarge" style={styles.title}>
          {t('profile.title')}
        </Text>
        <Text variant="bodyMedium" style={styles.subtitle}>
          {t('profile.lede')}
        </Text>
      </View>

      <View style={styles.section}>
        <Text variant="labelLarge" style={styles.sectionTitle}>
          {t('profile.account')}
        </Text>
        <View style={styles.card}>
          <SettingsRow
            label={t('profile.fullName')}
            value={profile.fullName?.trim() || t('common.notSet')}
            hint={t('profile.fullNameHint')}
            valueTestID="profile-full-name"
          />
          <View style={styles.divider} />
          <SettingsRow
            label={t('profile.verifiedPhone')}
            value={profile.phone}
            hint={t('profile.verifiedAt', {
              date: new Date(profile.phoneVerifiedAt).toLocaleString(locale),
            })}
            valueTestID="profile-phone"
          />
          <View style={styles.divider} />
          <SettingsRow
            label={t('profile.email')}
            value={profile.email ?? t('common.notSet')}
            hint={t('profile.emailHint')}
            valueTestID="profile-email"
          />
        </View>
      </View>

      <View style={styles.section}>
        <Text variant="labelLarge" style={styles.sectionTitle}>
          {t('profile.preferences')}
        </Text>
        <View style={styles.card}>
          <SettingsRow
            label={t('profile.notifications')}
            value={formatPreference(profile, t)}
            valueTestID="profile-notifications"
          />
          <View style={styles.divider} />
          <SettingsRow
            label={t('profile.publicName')}
            value={
              profile.publicNameVisible ? t('profile.publicVisible') : t('profile.publicHidden')
            }
            hint={t('profile.publicNameHint')}
            valueTestID="profile-public-name"
          />
        </View>
      </View>

      <View style={styles.section}>
        <Text variant="labelLarge" style={styles.sectionTitle}>
          {t('profile.session')}
        </Text>
        <View style={styles.card}>
          <SettingsRow
            label={t('profile.accountStatus')}
            value={`${accountStatus}${profile.active ? ` · ${t('profile.signedIn')}` : ''}`}
            valueTestID="profile-status"
          />
        </View>
      </View>

      <LanguageSwitcher />

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
          {t('profile.edit')}
        </Button>
        <Button
          mode="outlined"
          onPress={onChangePhone}
          style={styles.button}
          contentStyle={styles.controlContent}
          textColor={colors.brandDark}
          testID="change-phone-button"
        >
          {t('profile.changePhone')}
        </Button>
        <Link href={'/privacy' as Href} asChild>
          <Button
            mode="text"
            style={styles.button}
            contentStyle={styles.controlContent}
            textColor={colors.textSecondary}
            icon="shield-account-outline"
          >
            {t('profile.privacy')}
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
          {t('common.signOut')}
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

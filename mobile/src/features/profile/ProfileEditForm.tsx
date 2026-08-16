import { useEffect, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Banner, Button, HelperText, Switch, Text, TextInput } from 'react-native-paper';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import {
  TICKET_UPDATES_OPTIONS,
  profileEditSchema,
  profileToEditValues,
  type ProfileEditValues,
} from '@/schemas/citizenProfileSchema';
import { useI18n } from '@/i18n/LocaleProvider';
import { CitizenAuthApiError, PROFILE_UPDATE_SUCCESS_MESSAGE } from '@/services/api/citizenAuth';
import { colors, radii, spacing, touchTargetMin } from '@/theme';
import type { CitizenProfile, CitizenProfileUpdatePayload } from '@/types/citizen';

type ProfileEditFormProps = {
  profile: CitizenProfile;
  onSave: (patch: CitizenProfileUpdatePayload) => Promise<CitizenProfile>;
  onCancel: () => void;
};

export function ProfileEditForm({ profile, onSave, onCancel }: ProfileEditFormProps) {
  const { t } = useI18n();
  const [formError, setFormError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const requestInFlight = useRef(false);

  const {
    control,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ProfileEditValues>({
    resolver: zodResolver(profileEditSchema),
    defaultValues: profileToEditValues(profile),
    mode: 'onBlur',
  });

  useEffect(() => {
    reset(profileToEditValues(profile));
  }, [profile, reset]);

  const onSubmit = async (values: ProfileEditValues) => {
    if (requestInFlight.current) {
      return;
    }
    requestInFlight.current = true;
    setFormError(null);
    setSuccessMessage(null);

    try {
      const trimmedEmail = values.email.trim();
      const trimmedName = values.fullName.trim();
      await onSave({
        fullName: trimmedName ? trimmedName : null,
        email: trimmedEmail ? trimmedEmail : null,
        notificationPreferences: {
          ticketUpdates: values.ticketUpdates,
          announcements: values.announcements,
        },
        publicNameVisible: trimmedName ? values.publicNameVisible : false,
      });
      setSuccessMessage(PROFILE_UPDATE_SUCCESS_MESSAGE);
    } catch (error) {
      if (error instanceof CitizenAuthApiError) {
        setFormError(error.message);
      } else if (error instanceof Error) {
        setFormError(error.message);
      } else {
        setFormError(t('errors.generic'));
      }
    } finally {
      requestInFlight.current = false;
    }
  };

  return (
    <View style={styles.container} testID="profile-edit-form">
      <Text variant="titleLarge" style={styles.title}>
        {t('profile.edit')}
      </Text>
      <Text variant="bodyMedium" style={styles.subtitle}>
        {t('profile.editLede')}
      </Text>

      {successMessage ? (
        <Banner visible icon="check-circle" style={styles.banner} testID="profile-success-banner">
          {successMessage}
        </Banner>
      ) : null}

      {formError ? (
        <Banner visible icon="alert-circle" style={styles.banner} testID="profile-error-banner">
          {formError}
        </Banner>
      ) : null}

      <Controller
        control={control}
        name="fullName"
        render={({ field: { value, onChange, onBlur } }) => (
          <TextInput
            mode="outlined"
            label={t('profile.fullName')}
            value={value}
            onChangeText={onChange}
            onBlur={onBlur}
            error={Boolean(errors.fullName)}
            outlineColor={colors.border}
            activeOutlineColor={colors.brand}
            testID="edit-full-name-input"
          />
        )}
      />
      {errors.fullName ? (
        <HelperText type="error" visible testID="edit-full-name-error">
          {errors.fullName.message}
        </HelperText>
      ) : (
        <HelperText type="info" visible testID="edit-full-name-help">
          {t('profile.editNameHelp')}
        </HelperText>
      )}

      <Controller
        control={control}
        name="email"
        render={({ field: { value, onChange, onBlur } }) => (
          <TextInput
            mode="outlined"
            label={t('profile.email')}
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
            value={value}
            onChangeText={onChange}
            onBlur={onBlur}
            error={Boolean(errors.email)}
            outlineColor={colors.border}
            activeOutlineColor={colors.brand}
            testID="edit-email-input"
          />
        )}
      />
      {errors.email ? (
        <HelperText type="error" visible testID="edit-email-error">
          {errors.email.message}
        </HelperText>
      ) : (
        <HelperText type="info" visible testID="edit-email-help">
          {t('profile.editEmailHelp')}
        </HelperText>
      )}

      <Text variant="labelLarge" style={styles.sectionLabel}>
        {t('profile.ticketUpdatesLabel')}
      </Text>
      <Controller
        control={control}
        name="ticketUpdates"
        render={({ field: { value, onChange } }) => (
          <View style={styles.optionRow}>
            {TICKET_UPDATES_OPTIONS.map((option) => (
              <Button
                key={option.value}
                mode={value === option.value ? 'contained' : 'outlined'}
                compact
                onPress={() => onChange(option.value)}
                style={styles.optionButton}
                buttonColor={value === option.value ? colors.brand : undefined}
                textColor={value === option.value ? colors.textInverse : colors.brandDark}
                testID={`ticket-updates-${option.value}`}
              >
                {option.value === 'NONE'
                  ? t('profile.none')
                  : option.value === 'SMS'
                    ? t('profile.sms')
                    : option.value === 'EMAIL'
                      ? t('profile.emailOption')
                      : t('profile.smsAndEmail')}
              </Button>
            ))}
          </View>
        )}
      />
      {errors.ticketUpdates ? (
        <HelperText type="error" visible testID="edit-ticket-updates-error">
          {errors.ticketUpdates.message}
        </HelperText>
      ) : null}

      <Controller
        control={control}
        name="announcements"
        render={({ field: { value, onChange } }) => (
          <View style={styles.switchRow}>
            <Text variant="bodyLarge">{t('profile.announcements')}</Text>
            <Switch
              value={value}
              onValueChange={onChange}
              color={colors.brand}
              testID="edit-announcements-switch"
            />
          </View>
        )}
      />

      <Controller
        control={control}
        name="publicNameVisible"
        render={({ field: { value, onChange } }) => (
          <View style={styles.switchBlock}>
            <View style={styles.switchRow}>
              <Text variant="bodyLarge">{t('profile.showName')}</Text>
              <Switch
                value={value}
                onValueChange={onChange}
                color={colors.brand}
                testID="edit-public-name-switch"
              />
            </View>
            {errors.publicNameVisible ? (
              <HelperText type="error" visible testID="edit-public-name-error">
                {errors.publicNameVisible.message}
              </HelperText>
            ) : (
              <HelperText type="info" visible testID="edit-public-name-help">
                {t('profile.publicNameHelp')}
              </HelperText>
            )}
          </View>
        )}
      />

      <Button
        mode="contained"
        onPress={handleSubmit(onSubmit)}
        loading={isSubmitting}
        disabled={isSubmitting}
        style={styles.button}
        contentStyle={styles.controlContent}
        buttonColor={colors.brand}
        textColor={colors.textInverse}
        testID="save-profile-button"
      >
        {t('profile.saveChanges')}
      </Button>
      <Button
        mode="text"
        onPress={onCancel}
        disabled={isSubmitting}
        style={styles.button}
        contentStyle={styles.controlContent}
        textColor={colors.textSecondary}
        testID="cancel-edit-button"
      >
        {t('common.cancel')}
      </Button>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing[3],
  },
  title: {
    fontWeight: '700',
    color: colors.text,
  },
  subtitle: {
    color: colors.textSecondary,
    marginBottom: spacing[1],
  },
  banner: {
    marginBottom: spacing[1],
    borderRadius: radii.md,
  },
  sectionLabel: {
    color: colors.textMuted,
    marginTop: spacing[1],
  },
  optionRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing[2],
  },
  optionButton: {
    marginRight: 0,
    borderRadius: radii.md,
  },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing[3],
    minHeight: touchTargetMin,
  },
  switchBlock: {
    gap: 0,
  },
  button: {
    width: '100%',
    marginTop: spacing[1],
    borderRadius: radii.md,
  },
  controlContent: {
    minHeight: touchTargetMin,
  },
});

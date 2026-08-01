import { useEffect, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Banner, Button, HelperText, Switch, Text, TextInput } from 'react-native-paper';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import {
  EMAIL_NOT_LOGIN_MESSAGE,
  PUBLIC_NAME_VISIBLE_HELP,
  TICKET_UPDATES_OPTIONS,
  profileEditSchema,
  profileToEditValues,
  type ProfileEditValues,
} from '@/schemas/citizenProfileSchema';
import {
  CitizenAuthApiError,
  PROFILE_UPDATE_SUCCESS_MESSAGE,
} from '@/services/api/citizenAuth';
import type { CitizenProfile, CitizenProfileUpdatePayload } from '@/types/citizen';

type ProfileEditFormProps = {
  profile: CitizenProfile;
  onSave: (patch: CitizenProfileUpdatePayload) => Promise<CitizenProfile>;
  onCancel: () => void;
};

export function ProfileEditForm({ profile, onSave, onCancel }: ProfileEditFormProps) {
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
      await onSave({
        fullName: values.fullName.trim(),
        email: trimmedEmail ? trimmedEmail : null,
        notificationPreferences: {
          ticketUpdates: values.ticketUpdates,
          announcements: values.announcements,
        },
        publicNameVisible: values.publicNameVisible,
      });
      setSuccessMessage(PROFILE_UPDATE_SUCCESS_MESSAGE);
    } catch (error) {
      if (error instanceof CitizenAuthApiError) {
        setFormError(error.message);
      } else if (error instanceof Error) {
        setFormError(error.message);
      } else {
        setFormError('Something went wrong. Please try again.');
      }
    } finally {
      requestInFlight.current = false;
    }
  };

  return (
    <View style={styles.container} testID="profile-edit-form">
      <Text variant="titleLarge" style={styles.title}>
        Edit profile
      </Text>
      <Text variant="bodyMedium" style={styles.subtitle}>
        Update your name, optional email, notifications, and public-name visibility.
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
            label="Full name"
            value={value}
            onChangeText={onChange}
            onBlur={onBlur}
            error={Boolean(errors.fullName)}
            testID="edit-full-name-input"
          />
        )}
      />
      {errors.fullName ? (
        <HelperText type="error" visible testID="edit-full-name-error">
          {errors.fullName.message}
        </HelperText>
      ) : null}

      <Controller
        control={control}
        name="email"
        render={({ field: { value, onChange, onBlur } }) => (
          <TextInput
            mode="outlined"
            label="Email (optional)"
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
            value={value}
            onChangeText={onChange}
            onBlur={onBlur}
            error={Boolean(errors.email)}
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
          {EMAIL_NOT_LOGIN_MESSAGE}
        </HelperText>
      )}

      <Text variant="labelLarge" style={styles.sectionLabel}>
        Ticket update notifications
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
                testID={`ticket-updates-${option.value}`}
              >
                {option.label}
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
            <Text variant="bodyLarge">Municipality announcements</Text>
            <Switch
              value={value}
              onValueChange={onChange}
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
              <Text variant="bodyLarge">Show my name on reports</Text>
              <Switch
                value={value}
                onValueChange={onChange}
                testID="edit-public-name-switch"
              />
            </View>
            <HelperText type="info" visible testID="edit-public-name-help">
              {PUBLIC_NAME_VISIBLE_HELP}
            </HelperText>
          </View>
        )}
      />

      <Button
        mode="contained"
        onPress={handleSubmit(onSubmit)}
        loading={isSubmitting}
        disabled={isSubmitting}
        style={styles.button}
        testID="save-profile-button"
      >
        Save changes
      </Button>
      <Button mode="text" onPress={onCancel} disabled={isSubmitting} testID="cancel-edit-button">
        Cancel
      </Button>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: 12,
  },
  title: {
    fontWeight: '700',
  },
  subtitle: {
    color: '#475569',
    marginBottom: 4,
  },
  banner: {
    marginBottom: 4,
  },
  sectionLabel: {
    color: '#64748B',
    marginTop: 4,
  },
  optionRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  optionButton: {
    marginRight: 0,
  },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  switchBlock: {
    gap: 0,
  },
  button: {
    alignSelf: 'flex-start',
    marginTop: 4,
  },
});

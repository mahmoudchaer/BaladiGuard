import { useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Banner, Button, HelperText, Text, TextInput } from 'react-native-paper';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import {
  DEFAULT_PHONE_REGION,
  defaultPhoneOtpRequestValues,
  phoneOtpRequestSchema,
  type PhoneOtpRequestValues,
} from '@/schemas/citizenOtpSchema';
import { CitizenAuthApiError, requestCitizenOtp } from '@/services/api/citizenAuth';
import { colors, radii, spacing, touchTargetMin, typography } from '@/theme';
import type { CitizenOtpPurpose } from '@/types/citizen';
import { validatePhoneInput } from '@/utils/phone';

export type PhoneEntrySuccess = {
  challengeId: string;
  expiresIn: number;
  phone: string;
  region?: string;
};

type PhoneEntryFormProps = {
  onSuccess: (result: PhoneEntrySuccess) => void;
  purpose?: CitizenOtpPurpose;
  title?: string;
  subtitle?: string;
  submitLabel?: string;
};

export function PhoneEntryForm({
  onSuccess,
  purpose = 'LOGIN_OR_SIGNUP',
  title = 'Sign in with phone',
  subtitle = 'Enter your mobile number to receive a one-time verification code by SMS. No password needed.',
  submitLabel = 'Send verification code',
}: PhoneEntryFormProps) {
  const [formError, setFormError] = useState<string | null>(null);
  const [retryAfterSeconds, setRetryAfterSeconds] = useState<number | null>(null);
  const requestInFlight = useRef(false);

  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<PhoneOtpRequestValues>({
    resolver: zodResolver(phoneOtpRequestSchema),
    defaultValues: defaultPhoneOtpRequestValues,
    mode: 'onBlur',
  });

  const onSubmit = async (values: PhoneOtpRequestValues) => {
    if (requestInFlight.current) {
      return;
    }
    requestInFlight.current = true;
    setFormError(null);
    setRetryAfterSeconds(null);

    try {
      const validated = validatePhoneInput(values.phone, values.region ?? DEFAULT_PHONE_REGION);
      if (!validated.ok) {
        setFormError(validated.message);
        return;
      }

      const response = await requestCitizenOtp({
        phone: validated.phone,
        region: validated.region,
        purpose,
      });

      onSuccess({
        challengeId: response.challengeId,
        expiresIn: response.expiresIn,
        phone: validated.phone,
        region: validated.region,
      });
    } catch (error) {
      if (error instanceof CitizenAuthApiError) {
        setFormError(error.message);
        setRetryAfterSeconds(error.retryAfterSeconds);
      } else {
        setFormError('Something went wrong. Please try again.');
      }
    } finally {
      requestInFlight.current = false;
    }
  };

  return (
    <View style={styles.container}>
      <Text variant="titleLarge" style={styles.title}>
        {title}
      </Text>
      <Text variant="bodyMedium" style={styles.subtitle}>
        {subtitle}
      </Text>

      {formError ? (
        <Banner visible icon="alert-circle" style={styles.banner}>
          {`${formError}${retryAfterSeconds ? ` Try again in about ${retryAfterSeconds}s.` : ''}`}
        </Banner>
      ) : null}

      <View style={styles.fieldRow}>
        <Controller
          control={control}
          name="region"
          render={({ field: { value, onChange, onBlur } }) => (
            <TextInput
              mode="outlined"
              label="Region"
              placeholder="LB"
              autoCapitalize="characters"
              maxLength={2}
              value={value}
              onChangeText={(text) => onChange(text.toUpperCase())}
              onBlur={onBlur}
              outlineColor={colors.border}
              activeOutlineColor={colors.brand}
              style={styles.regionInput}
              testID="phone-region-input"
            />
          )}
        />
        <Controller
          control={control}
          name="phone"
          render={({ field: { value, onChange, onBlur } }) => (
            <TextInput
              mode="outlined"
              label="Phone number"
              keyboardType="phone-pad"
              placeholder="70123456"
              value={value}
              onChangeText={onChange}
              onBlur={onBlur}
              error={Boolean(errors.phone)}
              outlineColor={colors.border}
              activeOutlineColor={colors.brand}
              style={styles.phoneInput}
              testID="phone-input"
            />
          )}
        />
      </View>
      <HelperText type="info" visible style={styles.helper}>
        Use an ISO country code (for example LB) with a national number, or enter a full E.164
        number like +96170123456.
      </HelperText>
      {errors.phone ? (
        <HelperText type="error" visible testID="phone-error">
          {errors.phone.message}
        </HelperText>
      ) : null}

      <Button
        mode="contained"
        onPress={handleSubmit(onSubmit)}
        loading={isSubmitting}
        disabled={isSubmitting}
        style={styles.button}
        contentStyle={styles.controlContent}
        labelStyle={styles.controlLabel}
        buttonColor={colors.brand}
        textColor={colors.textInverse}
        testID="request-otp-button"
      >
        {submitLabel}
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
    lineHeight: 21,
  },
  banner: {
    marginBottom: spacing[1],
    borderRadius: radii.md,
  },
  fieldRow: {
    flexDirection: 'row',
    gap: spacing[2],
  },
  regionInput: {
    flexBasis: 96,
  },
  phoneInput: {
    flex: 1,
  },
  helper: {
    marginTop: -spacing[1],
  },
  button: {
    marginTop: spacing[1],
    width: '100%',
    borderRadius: radii.md,
  },
  controlContent: {
    minHeight: touchTargetMin,
  },
  controlLabel: {
    fontSize: typography.control,
    fontWeight: '700',
  },
});

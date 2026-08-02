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
import { validatePhoneInput } from '@/utils/phone';

export type PhoneEntrySuccess = {
  challengeId: string;
  expiresIn: number;
  phone: string;
  region?: string;
};

type PhoneEntryFormProps = {
  onSuccess: (result: PhoneEntrySuccess) => void;
};

export function PhoneEntryForm({ onSuccess }: PhoneEntryFormProps) {
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
        purpose: 'LOGIN_OR_SIGNUP',
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
        Sign in with phone
      </Text>
      <Text variant="bodyMedium" style={styles.subtitle}>
        Enter your mobile number to receive a one-time verification code. No password needed.
      </Text>

      {formError ? (
        <Banner visible icon="alert-circle" style={styles.banner}>
          {`${formError}${retryAfterSeconds ? ` Try again in about ${retryAfterSeconds}s.` : ''}`}
        </Banner>
      ) : null}

      <Controller
        control={control}
        name="region"
        render={({ field: { value, onChange, onBlur } }) => (
          <TextInput
            mode="outlined"
            label="Country / region"
            placeholder="LB"
            autoCapitalize="characters"
            maxLength={2}
            value={value}
            onChangeText={(text) => onChange(text.toUpperCase())}
            onBlur={onBlur}
            testID="phone-region-input"
          />
        )}
      />
      <HelperText type="info" visible>
        Use an ISO country code (for example LB) with a national number, or enter an E.164 number
        like +96170123456.
      </HelperText>

      <Controller
        control={control}
        name="phone"
        render={({ field: { value, onChange, onBlur } }) => (
          <TextInput
            mode="outlined"
            label="Phone number"
            keyboardType="phone-pad"
            placeholder="+96170123456 or 70123456"
            value={value}
            onChangeText={onChange}
            onBlur={onBlur}
            error={Boolean(errors.phone)}
            testID="phone-input"
          />
        )}
      />
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
        testID="request-otp-button"
      >
        Send verification code
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
  button: {
    marginTop: 8,
    alignSelf: 'flex-start',
  },
});

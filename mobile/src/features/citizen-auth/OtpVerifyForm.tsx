import { useCallback, useEffect, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Banner, Button, HelperText, Text, TextInput } from 'react-native-paper';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import {
  defaultOtpVerifyValues,
  otpVerifySchema,
  type OtpVerifyValues,
} from '@/schemas/citizenOtpSchema';
import {
  CitizenAuthApiError,
  requestCitizenOtp,
  verifyCitizenOtp,
} from '@/services/api/citizenAuth';
import type { CitizenOtpPurpose, CitizenOtpVerifyResponse } from '@/types/citizen';

type OtpVerifyFormProps = {
  challengeId: string;
  expiresIn: number;
  phone: string;
  region?: string;
  purpose?: CitizenOtpPurpose;
  onChallengeReplaced: (next: { challengeId: string; expiresIn: number }) => void;
  onVerified: (response: CitizenOtpVerifyResponse) => void;
};

function formatCountdown(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

export function OtpVerifyForm({
  challengeId,
  expiresIn,
  phone,
  region,
  purpose = 'LOGIN_OR_SIGNUP',
  onChallengeReplaced,
  onVerified,
}: OtpVerifyFormProps) {
  const [formError, setFormError] = useState<string | null>(null);
  const [retryAfterSeconds, setRetryAfterSeconds] = useState<number | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(expiresIn);
  const [resendCooldown, setResendCooldown] = useState(0);
  const [isResending, setIsResending] = useState(false);
  const requestInFlight = useRef(false);

  useEffect(() => {
    setSecondsLeft(expiresIn);
    const startedAt = Date.now();
    const timer = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedAt) / 1000);
      setSecondsLeft(Math.max(0, expiresIn - elapsed));
    }, 1000);
    return () => clearInterval(timer);
  }, [challengeId, expiresIn]);

  useEffect(() => {
    if (resendCooldown <= 0) {
      return;
    }
    const timer = setInterval(() => {
      setResendCooldown((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [resendCooldown]);

  const {
    control,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<OtpVerifyValues>({
    resolver: zodResolver(otpVerifySchema),
    defaultValues: defaultOtpVerifyValues,
    mode: 'onBlur',
  });

  const mapError = useCallback((error: unknown) => {
    if (error instanceof CitizenAuthApiError) {
      setFormError(error.message);
      setRetryAfterSeconds(error.retryAfterSeconds);
      return;
    }
    setFormError('Something went wrong. Please try again.');
  }, []);

  const onSubmit = async (values: OtpVerifyValues) => {
    if (requestInFlight.current) {
      return;
    }
    requestInFlight.current = true;
    setFormError(null);
    setRetryAfterSeconds(null);

    try {
      const response = await verifyCitizenOtp({
        challengeId,
        code: values.code.trim(),
      });
      onVerified(response);
    } catch (error) {
      mapError(error);
    } finally {
      requestInFlight.current = false;
    }
  };

  const onResend = async () => {
    if (isResending || resendCooldown > 0) {
      return;
    }
    setIsResending(true);
    setFormError(null);
    setRetryAfterSeconds(null);

    try {
      const response = await requestCitizenOtp({
        phone,
        region,
        purpose,
      });
      onChallengeReplaced({
        challengeId: response.challengeId,
        expiresIn: response.expiresIn,
      });
      reset(defaultOtpVerifyValues);
      setResendCooldown(30);
      setSecondsLeft(response.expiresIn);
    } catch (error) {
      mapError(error);
    } finally {
      setIsResending(false);
    }
  };

  const expired = secondsLeft <= 0;

  return (
    <View style={styles.container}>
      <Text variant="titleLarge" style={styles.title}>
        Enter verification code
      </Text>
      <Text variant="bodyMedium" style={styles.subtitle}>
        We sent a 6-digit code to {phone}. It expires in {formatCountdown(secondsLeft)}.
      </Text>

      {formError ? (
        <Banner visible icon="alert-circle" style={styles.banner}>
          {`${formError}${retryAfterSeconds ? ` Try again in about ${retryAfterSeconds}s.` : ''}`}
        </Banner>
      ) : null}

      {expired ? (
        <Banner visible icon="clock-outline" style={styles.banner}>
          This code has expired. Request a new one to continue.
        </Banner>
      ) : null}

      <Controller
        control={control}
        name="code"
        render={({ field: { value, onChange, onBlur } }) => (
          <TextInput
            mode="outlined"
            label="Verification code"
            keyboardType="number-pad"
            maxLength={6}
            value={value}
            onChangeText={onChange}
            onBlur={onBlur}
            error={Boolean(errors.code)}
            testID="otp-code-input"
          />
        )}
      />
      {errors.code ? (
        <HelperText type="error" visible testID="otp-code-error">
          {errors.code.message}
        </HelperText>
      ) : null}

      <Button
        mode="contained"
        onPress={handleSubmit(onSubmit)}
        loading={isSubmitting}
        disabled={isSubmitting || expired}
        style={styles.button}
        testID="verify-otp-button"
      >
        Verify code
      </Button>

      <Button
        mode="text"
        onPress={onResend}
        loading={isResending}
        disabled={isResending || resendCooldown > 0}
        style={styles.button}
        testID="resend-otp-button"
      >
        {resendCooldown > 0 ? `Resend code (${resendCooldown}s)` : 'Resend code'}
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
    alignSelf: 'flex-start',
  },
});

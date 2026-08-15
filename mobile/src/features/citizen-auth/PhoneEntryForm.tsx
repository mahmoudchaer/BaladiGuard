import { useMemo, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Banner, Button, HelperText, Text, TextInput } from 'react-native-paper';
import { Controller, useForm, useWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import { CountryDialingCodeSelector } from '@/components/CountryDialingCodeSelector';
import {
  DEFAULT_PHONE_REGION,
  defaultPhoneOtpRequestValues,
  phoneOtpRequestSchema,
  type PhoneOtpRequestValues,
} from '@/schemas/citizenOtpSchema';
import { CitizenAuthApiError, requestCitizenOtp } from '@/services/api/citizenAuth';
import { t } from '@/i18n';
import { colors, radii, spacing, touchTargetMin, typography } from '@/theme';
import type { CitizenOtpPurpose } from '@/types/citizen';
import { findCountryDialingOption, listCountryDialingOptions } from '@/utils/countryDialing';
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
  title,
  subtitle,
  submitLabel,
}: PhoneEntryFormProps) {
  const resolvedTitle = title ?? t('auth.phoneTitle');
  const resolvedSubtitle = subtitle ?? t('auth.phoneSubtitle');
  const resolvedSubmit = submitLabel ?? t('auth.sendCode');
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

  const selectedRegion = useWatch({ control, name: 'region' }) ?? DEFAULT_PHONE_REGION;
  const countryCatalog = useMemo(() => listCountryDialingOptions(), []);
  const selectedCountry = findCountryDialingOption(selectedRegion, 'en', countryCatalog);
  const nationalPlaceholder = selectedRegion === 'LB' ? '70123456' : 'National number';
  const nationalHelper = selectedCountry
    ? `Enter the national mobile number for ${selectedCountry.name} (without the +${selectedCountry.callingCode} prefix), or a full E.164 number like +${selectedCountry.callingCode}70123456.`
    : 'Enter a national mobile number for the selected country, or a full E.164 number like +96170123456.';

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
        {resolvedTitle}
      </Text>
      <Text variant="bodyMedium" style={styles.subtitle}>
        {resolvedSubtitle}
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
            <CountryDialingCodeSelector
              value={value ?? DEFAULT_PHONE_REGION}
              onChange={onChange}
              onBlur={onBlur}
              error={Boolean(errors.region)}
              testID="country-dialing-selector"
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
              placeholder={nationalPlaceholder}
              value={value}
              onChangeText={onChange}
              onBlur={onBlur}
              error={Boolean(errors.phone)}
              outlineColor={colors.border}
              activeOutlineColor={colors.brand}
              style={styles.phoneInput}
              testID="phone-input"
              accessibilityLabel="Phone number"
              accessibilityHint={
                selectedCountry
                  ? `National number for ${selectedCountry.name}, or full international number`
                  : 'National or full international phone number'
              }
            />
          )}
        />
      </View>
      <HelperText type="info" visible style={styles.helper} testID="phone-national-helper">
        {nationalHelper}
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
        {resolvedSubmit}
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
    flexWrap: 'wrap',
    gap: spacing[2],
    alignItems: 'flex-end',
  },
  phoneInput: {
    flexGrow: 1,
    flexShrink: 1,
    flexBasis: 160,
    minWidth: 140,
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

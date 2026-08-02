import { useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Banner, Button, HelperText, Text, TextInput } from 'react-native-paper';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import {
  defaultFullNameValues,
  fullNameSchema,
  type FullNameValues,
} from '@/schemas/citizenOtpSchema';
import { CitizenAuthApiError } from '@/services/api/citizenAuth';

type FullNameFormProps = {
  onSubmitName: (fullName: string) => Promise<void>;
};

export function FullNameForm({ onSubmitName }: FullNameFormProps) {
  const [formError, setFormError] = useState<string | null>(null);
  const requestInFlight = useRef(false);

  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FullNameValues>({
    resolver: zodResolver(fullNameSchema),
    defaultValues: defaultFullNameValues,
    mode: 'onBlur',
  });

  const onSubmit = async (values: FullNameValues) => {
    if (requestInFlight.current) {
      return;
    }
    requestInFlight.current = true;
    setFormError(null);

    try {
      await onSubmitName(values.fullName.trim());
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
    <View style={styles.container}>
      <Text variant="titleLarge" style={styles.title}>
        Almost done
      </Text>
      <Text variant="bodyMedium" style={styles.subtitle}>
        Add your full name to finish setting up your account. Email is optional and is not required
        to sign in.
      </Text>

      {formError ? (
        <Banner visible icon="alert-circle" style={styles.banner}>
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
            testID="full-name-input"
          />
        )}
      />
      {errors.fullName ? (
        <HelperText type="error" visible testID="full-name-error">
          {errors.fullName.message}
        </HelperText>
      ) : null}

      <Button
        mode="contained"
        onPress={handleSubmit(onSubmit)}
        loading={isSubmitting}
        disabled={isSubmitting}
        style={styles.button}
        testID="save-full-name-button"
      >
        Continue
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

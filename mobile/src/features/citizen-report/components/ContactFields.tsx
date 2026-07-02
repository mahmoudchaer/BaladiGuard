import { StyleSheet, View } from 'react-native';
import { HelperText, Text, TextInput } from 'react-native-paper';
import type { Control, FieldErrors } from 'react-hook-form';
import { Controller } from 'react-hook-form';

import type { ReportFormValues } from '@/schemas/reportFormSchema';

type ContactFieldsProps = {
  control: Control<ReportFormValues>;
  errors: FieldErrors<ReportFormValues>;
};

export function ContactFields({ control, errors }: ContactFieldsProps) {
  return (
    <View style={styles.container}>
      <Text variant="titleMedium" style={styles.label}>
        Contact details
      </Text>
      <Text variant="bodySmall" style={styles.helper}>
        Provide at least a phone number or email so the municipality can follow up if needed.
      </Text>

      <Controller
        control={control}
        name="contactName"
        render={({ field: { value, onChange, onBlur } }) => (
          <TextInput
            mode="outlined"
            label="Name (optional)"
            value={value}
            onChangeText={onChange}
            onBlur={onBlur}
          />
        )}
      />

      <Controller
        control={control}
        name="phone"
        render={({ field: { value, onChange, onBlur } }) => (
          <TextInput
            mode="outlined"
            label="Phone"
            keyboardType="phone-pad"
            placeholder="+96170123456"
            value={value}
            onChangeText={onChange}
            onBlur={onBlur}
            error={Boolean(errors.phone)}
          />
        )}
      />

      <Controller
        control={control}
        name="email"
        render={({ field: { value, onChange, onBlur } }) => (
          <TextInput
            mode="outlined"
            label="Email"
            keyboardType="email-address"
            autoCapitalize="none"
            value={value}
            onChangeText={onChange}
            onBlur={onBlur}
            error={Boolean(errors.email)}
          />
        )}
      />

      {errors.phone ? (
        <HelperText type="error" visible>
          {errors.phone.message}
        </HelperText>
      ) : null}
      {errors.email ? (
        <HelperText type="error" visible>
          {errors.email.message}
        </HelperText>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: 10,
  },
  label: {
    fontWeight: '600',
  },
  helper: {
    color: '#64748B',
  },
});

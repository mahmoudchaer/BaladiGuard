import { StyleSheet, View } from 'react-native';
import { HelperText, Text, TextInput } from 'react-native-paper';
import type { Control, FieldErrors } from 'react-hook-form';
import { Controller } from 'react-hook-form';

import { colors, spacing } from '@/theme';
import type { ReportFormValues } from '@/schemas/reportFormSchema';

type DetailsStepProps = {
  control: Control<ReportFormValues>;
  errors: FieldErrors<ReportFormValues>;
};

export function DetailsStep({ control, errors }: DetailsStepProps) {
  return (
    <View style={styles.container}>
      <Text variant="titleMedium" style={styles.label}>
        What&apos;s the problem?
      </Text>
      <Text variant="bodySmall" style={styles.helper}>
        Describe the issue in plain language — a pothole, broken streetlight, waste pile, water
        leak, and so on.
      </Text>
      <Controller
        control={control}
        name="description"
        render={({ field: { value, onChange, onBlur } }) => (
          <TextInput
            mode="outlined"
            label="Describe the issue"
            placeholder="e.g. Large pothole blocking the right lane near the school gate."
            value={value}
            onChangeText={onChange}
            onBlur={onBlur}
            multiline
            numberOfLines={6}
            style={styles.textArea}
            error={Boolean(errors.description)}
          />
        )}
      />
      {errors.description ? (
        <HelperText type="error" visible>
          {errors.description.message}
        </HelperText>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing[2],
  },
  label: {
    fontWeight: '600',
  },
  helper: {
    color: colors.textMuted,
  },
  textArea: {
    minHeight: 160,
  },
});

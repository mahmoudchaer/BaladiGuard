import { StyleSheet, View } from 'react-native';
import { Chip, HelperText, Text, TextInput } from 'react-native-paper';
import type { Control, FieldErrors, UseFormSetValue } from 'react-hook-form';
import { Controller } from 'react-hook-form';

import { PLACEHOLDER_LOCATIONS } from '@/constants/locations';
import type { ReportFormValues } from '@/schemas/reportFormSchema';

type LocationFieldsProps = {
  control: Control<ReportFormValues>;
  errors: FieldErrors<ReportFormValues>;
  setValue: UseFormSetValue<ReportFormValues>;
  selectedPlaceholderId?: string;
  onSelectPlaceholder: (id: string) => void;
};

export function LocationFields({
  control,
  errors,
  setValue,
  selectedPlaceholderId,
  onSelectPlaceholder,
}: LocationFieldsProps) {
  return (
    <View style={styles.container}>
      <Text variant="titleMedium" style={styles.label}>
        Location
      </Text>
      <Text variant="bodySmall" style={styles.helper}>
        Type an address or pick a sample location. Map coordinates are required until GPS and map
        selection are available.
      </Text>

      <Controller
        control={control}
        name="addressText"
        render={({ field: { value, onChange, onBlur } }) => (
          <TextInput
            mode="outlined"
            label="Address or landmark"
            placeholder="e.g. Near AUB Main Gate, Hamra"
            value={value}
            onChangeText={(text) => {
              onChange(text);
              setValue('latitude', undefined);
              setValue('longitude', undefined);
              setValue('locationSource', 'MANUAL');
              onSelectPlaceholder('');
            }}
            onBlur={onBlur}
            error={Boolean(errors.addressText)}
          />
        )}
      />

      <View style={styles.chipRow}>
        {PLACEHOLDER_LOCATIONS.map((location) => (
          <Chip
            key={location.id}
            selected={selectedPlaceholderId === location.id}
            onPress={() => {
              onSelectPlaceholder(location.id);
              setValue('addressText', location.addressText, { shouldValidate: true });
              setValue('latitude', location.latitude);
              setValue('longitude', location.longitude);
              setValue('locationSource', 'PLACEHOLDER');
            }}
            style={styles.chip}
          >
            {location.label}
          </Chip>
        ))}
      </View>

      <View style={styles.mapPlaceholder}>
        <Text variant="labelLarge">Map picker placeholder</Text>
        <Text variant="bodySmall" style={styles.mapText}>
          Interactive map selection will be added in a later sprint. For now, use the address field
          or sample locations above.
        </Text>
      </View>

      {errors.addressText ? (
        <HelperText type="error" visible>
          {errors.addressText.message}
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
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  chip: {
    marginBottom: 4,
  },
  mapPlaceholder: {
    borderWidth: 1,
    borderColor: '#CBD5E1',
    borderStyle: 'dashed',
    borderRadius: 12,
    padding: 16,
    backgroundColor: '#F8FAFC',
    gap: 6,
  },
  mapText: {
    color: '#64748B',
  },
});

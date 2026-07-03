import { Image, StyleSheet, View } from 'react-native';
import { Button, HelperText, Text } from 'react-native-paper';
import * as ImagePicker from 'expo-image-picker';
import type { Control, FieldErrors, UseFormSetValue } from 'react-hook-form';
import { Controller } from 'react-hook-form';

import type { ReportFormValues } from '@/schemas/reportFormSchema';

type PhotoPickerFieldProps = {
  control: Control<ReportFormValues>;
  errors: FieldErrors<ReportFormValues>;
  setValue: UseFormSetValue<ReportFormValues>;
};

export function PhotoPickerField({ control, errors, setValue }: PhotoPickerFieldProps) {
  return (
    <Controller
      control={control}
      name="photoUri"
      render={({ field: { value, onChange } }) => (
        <View style={styles.container}>
          <Text variant="titleMedium" style={styles.label}>
            Photo
          </Text>
          <Text variant="bodySmall" style={styles.helper}>
            Attach a clear photo of the infrastructure issue.
          </Text>

          {value ? (
            <View style={styles.previewWrap}>
              <Image source={{ uri: value }} style={styles.preview} />
              <Button mode="outlined" onPress={() => onChange('')}>
                Remove photo
              </Button>
            </View>
          ) : (
            <Button
              mode="contained-tonal"
              icon="camera"
              onPress={async () => {
                const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
                if (!permission.granted) {
                  return;
                }

                const result = await ImagePicker.launchImageLibraryAsync({
                  mediaTypes: ImagePicker.MediaTypeOptions.Images,
                  allowsEditing: true,
                  quality: 0.8,
                });

                if (!result.canceled && result.assets[0]) {
                  const asset = result.assets[0];
                  onChange(asset.uri);
                  setValue('photoFileName', asset.fileName ?? `photo-${Date.now()}.jpg`);
                  setValue('photoContentType', asset.mimeType ?? 'image/jpeg');
                }
              }}
            >
              Choose photo
            </Button>
          )}

          {errors.photoUri ? (
            <HelperText type="error" visible>
              {errors.photoUri.message}
            </HelperText>
          ) : null}
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  container: {
    gap: 8,
  },
  label: {
    fontWeight: '600',
  },
  helper: {
    color: '#64748B',
  },
  previewWrap: {
    gap: 12,
  },
  preview: {
    width: '100%',
    height: 220,
    borderRadius: 12,
    backgroundColor: '#E2E8F0',
  },
});

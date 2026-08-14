import { useState } from 'react';
import { Image, StyleSheet, View } from 'react-native';
import { Button, HelperText, Text } from 'react-native-paper';
import * as ImagePicker from 'expo-image-picker';
import type { Control, FieldErrors, UseFormSetValue } from 'react-hook-form';
import { Controller } from 'react-hook-form';

import { colors, radii, spacing, touchTargetMin } from '@/theme';
import type { ReportFormValues } from '@/schemas/reportFormSchema';

type PhotoPickerFieldProps = {
  control: Control<ReportFormValues>;
  errors: FieldErrors<ReportFormValues>;
  setValue: UseFormSetValue<ReportFormValues>;
  onPhotoChanged?: () => void;
};

type PickerSource = 'camera' | 'library';

const CAMERA_PERMISSION_MESSAGE =
  'Camera access is needed to take a photo. You can choose one from your gallery instead, or enable camera access in your device settings.';
const LIBRARY_PERMISSION_MESSAGE =
  'Photo library access is needed to attach a photo. Enable it in your device settings and try again.';
const PICKER_FAILURE_MESSAGE =
  'Something went wrong while opening the camera or gallery. Please try again.';

export function PhotoPickerField({
  control,
  errors,
  setValue,
  onPhotoChanged,
}: PhotoPickerFieldProps) {
  const [permissionError, setPermissionError] = useState<string | null>(null);
  const [activePicker, setActivePicker] = useState<PickerSource | null>(null);

  const applyAsset = (asset: ImagePicker.ImagePickerAsset, onChange: (uri: string) => void) => {
    onPhotoChanged?.();
    onChange(asset.uri);
    setValue('photoFileName', asset.fileName ?? `photo-${Date.now()}.jpg`);
    setValue('photoContentType', asset.mimeType ?? 'image/jpeg');
  };

  const pickFrom = async (source: PickerSource, onChange: (uri: string) => void) => {
    setPermissionError(null);
    setActivePicker(source);
    try {
      const permission =
        source === 'camera'
          ? await ImagePicker.requestCameraPermissionsAsync()
          : await ImagePicker.requestMediaLibraryPermissionsAsync();

      if (!permission.granted) {
        setPermissionError(
          source === 'camera' ? CAMERA_PERMISSION_MESSAGE : LIBRARY_PERMISSION_MESSAGE,
        );
        return;
      }

      const result =
        source === 'camera'
          ? await ImagePicker.launchCameraAsync({ allowsEditing: true, quality: 0.8 })
          : await ImagePicker.launchImageLibraryAsync({
              mediaTypes: ['images'],
              allowsEditing: true,
              quality: 0.8,
            });

      if (!result.canceled && result.assets[0]) {
        applyAsset(result.assets[0], onChange);
      }
    } catch {
      setPermissionError(PICKER_FAILURE_MESSAGE);
    } finally {
      setActivePicker(null);
    }
  };

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
            Attach a clear photo of the infrastructure issue so crews know what to expect.
          </Text>

          {value ? (
            <View style={styles.previewWrap}>
              <Image source={{ uri: value }} style={styles.preview} />
              <View style={styles.actionRow}>
                <Button
                  mode="outlined"
                  style={styles.actionButton}
                  contentStyle={styles.actionButtonContent}
                  loading={activePicker === 'library'}
                  disabled={activePicker !== null}
                  onPress={() => {
                    void pickFrom('library', onChange);
                  }}
                >
                  Replace photo
                </Button>
                <Button
                  mode="text"
                  textColor={colors.danger}
                  style={styles.actionButton}
                  contentStyle={styles.actionButtonContent}
                  onPress={() => {
                    onPhotoChanged?.();
                    onChange('');
                    setValue('photoFileName', '');
                    setValue('photoContentType', '');
                    setPermissionError(null);
                  }}
                >
                  Remove photo
                </Button>
              </View>
            </View>
          ) : (
            <View style={styles.actionRow}>
              <Button
                mode="contained-tonal"
                icon="camera"
                style={styles.actionButton}
                contentStyle={styles.actionButtonContent}
                loading={activePicker === 'camera'}
                disabled={activePicker !== null}
                onPress={() => {
                  void pickFrom('camera', onChange);
                }}
              >
                Take photo
              </Button>
              <Button
                mode="outlined"
                icon="image-multiple"
                style={styles.actionButton}
                contentStyle={styles.actionButtonContent}
                loading={activePicker === 'library'}
                disabled={activePicker !== null}
                onPress={() => {
                  void pickFrom('library', onChange);
                }}
              >
                Choose photo
              </Button>
            </View>
          )}

          {permissionError ? (
            <HelperText type="error" visible>
              {permissionError}
            </HelperText>
          ) : null}

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
    gap: spacing[2],
  },
  label: {
    fontWeight: '600',
  },
  helper: {
    color: colors.textMuted,
  },
  actionRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing[2],
  },
  actionButton: {
    borderRadius: radii.md,
    flexGrow: 1,
  },
  actionButtonContent: {
    minHeight: touchTargetMin,
  },
  previewWrap: {
    gap: spacing[3],
  },
  preview: {
    width: '100%',
    height: 220,
    borderRadius: radii.lg,
    backgroundColor: colors.surfaceSubtle,
  },
});

import { Platform, StyleSheet, View } from 'react-native';
import { ActivityIndicator, Button, Chip, HelperText, Text, TextInput } from 'react-native-paper';
import type { Control, FieldErrors, UseFormSetValue } from 'react-hook-form';
import { Controller, useWatch } from 'react-hook-form';
import { useEffect, useRef, useState } from 'react';
import MapView, { Marker, type MapPressEvent, type Region } from 'react-native-maps';

import { PLACEHOLDER_LOCATIONS } from '@/constants/locations';
import type { ReportFormValues } from '@/schemas/reportFormSchema';
import { getCurrentDeviceLocation } from '@/services/deviceLocation';
import { colors, radii, spacing, touchTargetMin, typography } from '@/theme';
import {
  defaultMapRegion,
  locationSourceForMapPin,
  validateLocation,
} from '@/services/api/locations';

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
  const [isValidating, setIsValidating] = useState(false);
  const [isDetectingGps, setIsDetectingGps] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [gpsHint, setGpsHint] = useState<string | null>(null);
  // Manual entry starts collapsed; a confirmed pin keeps it tucked away until requested.
  const [manualOpen, setManualOpen] = useState(false);

  const addressText = useWatch({ control, name: 'addressText' });
  const latitude = useWatch({ control, name: 'latitude' });
  const longitude = useWatch({ control, name: 'longitude' });
  const locationSource = useWatch({ control, name: 'locationSource' });

  const mapRegion: Region = defaultMapRegion({ latitude, longitude });
  const hasPin = latitude !== undefined && longitude !== undefined;
  const showManualEntry = manualOpen || (!hasPin && !isDetectingGps);

  // Prevent a late GPS response from overwriting a choice the user already made.
  const userAdjustedRef = useRef(false);
  const autoDetectStartedRef = useRef(false);
  // Bumps on each GPS request so an older in-flight response cannot win a race.
  const gpsRequestIdRef = useRef(0);

  const markUserAdjusted = () => {
    userAdjustedRef.current = true;
  };

  const applyValidatedLocation = (location: {
    latitude: number;
    longitude: number;
    addressText: string;
    source: ReportFormValues['locationSource'];
  }) => {
    setValue('addressText', location.addressText, { shouldValidate: true });
    setValue('latitude', location.latitude, { shouldValidate: true });
    setValue('longitude', location.longitude, { shouldValidate: true });
    setValue('locationSource', location.source, { shouldValidate: true });
  };

  const shouldApplyGpsResult = (requestId: number) =>
    !userAdjustedRef.current && requestId === gpsRequestIdRef.current;

  const applyGpsCoordinates = async (
    coordinates: { latitude: number; longitude: number },
    requestId: number,
  ) => {
    if (!shouldApplyGpsResult(requestId)) {
      return;
    }

    setIsValidating(true);
    setLocationError(null);
    onSelectPlaceholder('');

    try {
      const result = await validateLocation({
        latitude: coordinates.latitude,
        longitude: coordinates.longitude,
      });

      if (!shouldApplyGpsResult(requestId)) {
        return;
      }

      if (result.success && result.location) {
        applyValidatedLocation({
          ...result.location,
          source: 'GPS',
        });
      } else {
        applyValidatedLocation({
          latitude: coordinates.latitude,
          longitude: coordinates.longitude,
          addressText: 'Current location',
          source: 'GPS',
        });
      }
      setGpsHint('Using your current location. You can move the pin or look up another address.');
    } catch {
      if (!shouldApplyGpsResult(requestId)) {
        return;
      }
      applyValidatedLocation({
        latitude: coordinates.latitude,
        longitude: coordinates.longitude,
        addressText: 'Current location',
        source: 'GPS',
      });
      setGpsHint('Using your current GPS coordinates. You can adjust the pin if needed.');
    } finally {
      setIsValidating(false);
    }
  };

  const detectCurrentLocation = async (options?: { force?: boolean }) => {
    // force only clears a prior override at button press; manual changes during the
    // in-flight request still block applying the late GPS result.
    if (options?.force) {
      userAdjustedRef.current = false;
    }

    const requestId = ++gpsRequestIdRef.current;
    setIsDetectingGps(true);
    setLocationError(null);
    setGpsHint(null);

    try {
      const result = await getCurrentDeviceLocation();
      if (!result.ok) {
        if (shouldApplyGpsResult(requestId)) {
          setGpsHint(result.message);
        }
        return;
      }

      await applyGpsCoordinates(result.coordinates, requestId);
    } finally {
      if (requestId === gpsRequestIdRef.current) {
        setIsDetectingGps(false);
      }
    }
  };

  useEffect(() => {
    if (autoDetectStartedRef.current) {
      return;
    }
    autoDetectStartedRef.current = true;
    void detectCurrentLocation();
    // Auto-detect once when the location step first opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleLookupAddress = async () => {
    const query = addressText?.trim() ?? '';
    if (query.length < 3) {
      setLocationError('Enter at least 3 characters before looking up an address.');
      return;
    }

    markUserAdjusted();
    setIsValidating(true);
    setLocationError(null);
    setGpsHint(null);
    try {
      const result = await validateLocation({ addressText: query });
      if (!result.success || !result.location) {
        throw new Error(result.message ?? 'Unable to validate that location.');
      }
      onSelectPlaceholder('');
      applyValidatedLocation({
        ...result.location,
        source: 'MANUAL',
      });
    } catch (error) {
      setLocationError(
        error instanceof Error ? error.message : 'Unable to validate that location.',
      );
      setValue('latitude', undefined, { shouldValidate: true });
      setValue('longitude', undefined, { shouldValidate: true });
    } finally {
      setIsValidating(false);
    }
  };

  const handleMapPress = async (event: MapPressEvent) => {
    const coordinate = event.nativeEvent.coordinate;
    markUserAdjusted();
    setIsValidating(true);
    setLocationError(null);
    setGpsHint(null);
    onSelectPlaceholder('');

    try {
      const result = await validateLocation({
        latitude: coordinate.latitude,
        longitude: coordinate.longitude,
      });
      if (!result.success || !result.location) {
        throw new Error(result.message ?? 'Unable to validate that map point.');
      }
      applyValidatedLocation({
        ...result.location,
        source: locationSourceForMapPin(locationSource),
      });
    } catch (error) {
      setLocationError(
        error instanceof Error ? error.message : 'Unable to validate that map point.',
      );
      setValue('latitude', undefined, { shouldValidate: true });
      setValue('longitude', undefined, { shouldValidate: true });
    } finally {
      setIsValidating(false);
    }
  };

  const isBusy = isValidating || isDetectingGps;

  return (
    <View style={styles.container}>
      <Text variant="titleMedium" style={styles.label}>
        Location
      </Text>
      <Text variant="bodySmall" style={styles.helper}>
        We try to find your current location automatically. Confirm it on the map, or enter an
        address if that&apos;s easier.
      </Text>

      <Button
        mode="contained-tonal"
        onPress={() => {
          void detectCurrentLocation({ force: true });
        }}
        disabled={isBusy}
        icon="crosshairs-gps"
        style={styles.gpsButton}
        contentStyle={styles.gpsButtonContent}
      >
        {isDetectingGps ? 'Detecting location…' : 'Use my current location'}
      </Button>

      {isBusy ? (
        <View style={styles.validatingRow}>
          <ActivityIndicator animating color={colors.brand} />
          <Text variant="bodySmall" style={styles.validatingText}>
            {isDetectingGps ? 'Detecting your current location…' : 'Checking location…'}
          </Text>
        </View>
      ) : null}

      {gpsHint ? (
        <HelperText type="info" visible>
          {gpsHint}
        </HelperText>
      ) : null}

      {hasPin ? (
        <View style={styles.confirmedBlock}>
          {Platform.OS === 'web' ? (
            <View style={styles.mapPlaceholder}>
              <Text variant="labelLarge">Map picker</Text>
              <Text variant="bodySmall" style={styles.mapText}>
                Interactive map pins are available in the iOS/Android app. On web, use current
                location, address lookup, or a sample location.
              </Text>
            </View>
          ) : (
            <View style={styles.mapContainer}>
              <MapView
                style={styles.map}
                initialRegion={mapRegion}
                region={mapRegion}
                onPress={(event) => {
                  void handleMapPress(event);
                }}
              >
                <Marker
                  coordinate={{
                    latitude: latitude as number,
                    longitude: longitude as number,
                  }}
                  title="Report location"
                  description={addressText}
                />
              </MapView>
              <Text variant="bodySmall" style={styles.mapHint}>
                Tap the map to move the pin.
              </Text>
            </View>
          )}

          <View style={styles.confirmedRow}>
            <Text variant="bodyMedium" style={styles.confirmedText}>
              Pinned near {addressText || 'the selected point'}
            </Text>
            <Button
              mode="text"
              compact
              textColor={colors.brandDark}
              onPress={() => setManualOpen(true)}
            >
              Change
            </Button>
          </View>
        </View>
      ) : null}

      {showManualEntry ? (
        <View style={styles.manualBlock}>
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
                  markUserAdjusted();
                  onChange(text);
                  setLocationError(null);
                  setGpsHint(null);
                  setValue('latitude', undefined);
                  setValue('longitude', undefined);
                  setValue('locationSource', 'MANUAL');
                  if (selectedPlaceholderId) {
                    onSelectPlaceholder('');
                  }
                }}
                onBlur={onBlur}
                error={Boolean(errors.addressText) || Boolean(locationError)}
              />
            )}
          />

          <Button
            mode="outlined"
            onPress={() => {
              void handleLookupAddress();
            }}
            disabled={isBusy}
            icon="map-search"
            style={styles.lookupButton}
            contentStyle={styles.lookupButtonContent}
          >
            {isValidating && !isDetectingGps ? 'Validating…' : 'Look up address'}
          </Button>

          <Text variant="bodySmall" style={styles.helper}>
            Or pick a sample Beirut location:
          </Text>
          <View style={styles.chipRow}>
            {PLACEHOLDER_LOCATIONS.map((location) => (
              <Chip
                key={location.id}
                selected={selectedPlaceholderId === location.id}
                onPress={() => {
                  markUserAdjusted();
                  onSelectPlaceholder(location.id);
                  setLocationError(null);
                  setGpsHint(null);
                  applyValidatedLocation({
                    latitude: location.latitude,
                    longitude: location.longitude,
                    addressText: location.addressText,
                    source: 'PLACEHOLDER',
                  });
                }}
                style={styles.chip}
                disabled={isBusy}
              >
                {location.label}
              </Chip>
            ))}
          </View>
        </View>
      ) : null}

      {locationError ? (
        <HelperText type="error" visible>
          {locationError}
        </HelperText>
      ) : null}

      {errors.addressText ? (
        <HelperText type="error" visible>
          {errors.addressText.message}
        </HelperText>
      ) : null}

      {hasPin ? (
        <HelperText type="info" visible>
          Coordinates ready ({latitude?.toFixed(5)}, {longitude?.toFixed(5)})
        </HelperText>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing[3],
  },
  label: {
    fontWeight: '600',
  },
  helper: {
    color: colors.textMuted,
  },
  gpsButton: {
    borderRadius: radii.md,
  },
  gpsButtonContent: {
    minHeight: touchTargetMin,
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing[2],
  },
  chip: {
    marginBottom: spacing[1],
  },
  confirmedBlock: {
    gap: spacing[2],
  },
  confirmedRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing[2],
  },
  confirmedText: {
    color: colors.text,
    flexShrink: 1,
  },
  manualBlock: {
    gap: spacing[2],
    padding: spacing[3],
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSubtle,
  },
  lookupButton: {
    borderRadius: radii.md,
  },
  lookupButtonContent: {
    minHeight: touchTargetMin,
  },
  mapContainer: {
    borderRadius: radii.lg,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: colors.border,
    gap: spacing[1],
  },
  map: {
    width: '100%',
    height: 220,
  },
  mapHint: {
    color: colors.textMuted,
    paddingHorizontal: spacing[3],
    paddingBottom: spacing[2],
  },
  mapPlaceholder: {
    borderWidth: 1,
    borderColor: colors.border,
    borderStyle: 'dashed',
    borderRadius: radii.lg,
    padding: spacing[4],
    backgroundColor: colors.surfaceSubtle,
    gap: spacing[2],
  },
  mapText: {
    color: colors.textMuted,
  },
  validatingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing[2],
  },
  validatingText: {
    color: colors.textSecondary,
    fontSize: typography.bodyCompact,
  },
});

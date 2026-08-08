import * as Location from 'expo-location';

export type DeviceCoordinates = {
  latitude: number;
  longitude: number;
  accuracyMeters?: number | null;
};

export type DeviceLocationResult =
  | { ok: true; coordinates: DeviceCoordinates }
  | { ok: false; reason: 'permission_denied' | 'unavailable' | 'timeout'; message: string };

/**
 * Request foreground location permission and read the device's current GPS position.
 */
export async function getCurrentDeviceLocation(): Promise<DeviceLocationResult> {
  try {
    const permission = await Location.requestForegroundPermissionsAsync();
    if (!permission.granted) {
      return {
        ok: false,
        reason: 'permission_denied',
        message:
          'Location permission is required to use your current position. You can enable it in your device settings, or choose a place on the map instead.',
      };
    }

    const position = await Location.getCurrentPositionAsync({
      accuracy: Location.Accuracy.Balanced,
    });

    return {
      ok: true,
      coordinates: {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracyMeters: position.coords.accuracy,
      },
    };
  } catch {
    return {
      ok: false,
      reason: 'unavailable',
      message: 'Unable to read your current location right now.',
    };
  }
}

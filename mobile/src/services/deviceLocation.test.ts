import { afterEach, describe, expect, it, vi } from 'vitest';

const { requestForegroundPermissionsAsync, getCurrentPositionAsync, Accuracy } = vi.hoisted(() => ({
  requestForegroundPermissionsAsync: vi.fn(),
  getCurrentPositionAsync: vi.fn(),
  Accuracy: { Balanced: 3 },
}));

vi.mock('expo-location', () => ({
  requestForegroundPermissionsAsync,
  getCurrentPositionAsync,
  Accuracy,
}));

afterEach(() => {
  vi.clearAllMocks();
  vi.resetModules();
});

describe('getCurrentDeviceLocation', () => {
  it('returns coordinates when permission is granted', async () => {
    requestForegroundPermissionsAsync.mockResolvedValue({ granted: true });
    getCurrentPositionAsync.mockResolvedValue({
      coords: { latitude: 33.9, longitude: 35.5, accuracy: 12 },
    });

    const { getCurrentDeviceLocation } = await import('@/services/deviceLocation');
    const result = await getCurrentDeviceLocation();

    expect(result).toEqual({
      ok: true,
      coordinates: {
        latitude: 33.9,
        longitude: 35.5,
        accuracyMeters: 12,
      },
    });
  });

  it('returns permission_denied when the user blocks location access', async () => {
    requestForegroundPermissionsAsync.mockResolvedValue({ granted: false });

    const { getCurrentDeviceLocation } = await import('@/services/deviceLocation');
    const result = await getCurrentDeviceLocation();

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.reason).toBe('permission_denied');
    }
    expect(getCurrentPositionAsync).not.toHaveBeenCalled();
  });

  it('returns unavailable when GPS reading fails', async () => {
    requestForegroundPermissionsAsync.mockResolvedValue({ granted: true });
    getCurrentPositionAsync.mockRejectedValue(new Error('GPS offline'));

    const { getCurrentDeviceLocation } = await import('@/services/deviceLocation');
    const result = await getCurrentDeviceLocation();

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.reason).toBe('unavailable');
    }
  });
});

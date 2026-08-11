/**
 * Local photo URI reachability for report drafts (#258).
 *
 * Image-picker `file://` / `content://` URIs may disappear after process restart.
 * Before upload and on draft restore we use Expo FileSystem's existence check
 * so dead references are cleared and the user is asked to re-pick — without
 * relying on unreliable `fetch(file://…)` probes.
 */

import * as FileSystem from 'expo-file-system';

export type LocalPhotoCheckResult = {
  ok: boolean;
  /** User-facing reason when the reference is unusable. */
  reason?: 'missing' | 'empty' | 'unreachable';
};

/** True for local device schemes that can vanish after restart. */
export function isLocalDevicePhotoUri(uri: string): boolean {
  const value = uri.trim().toLowerCase();
  return (
    value.startsWith('file:') ||
    value.startsWith('content:') ||
    value.startsWith('ph://') ||
    value.startsWith('assets-library:')
  );
}

/**
 * Probe whether a local photo URI is still readable on device.
 * Remote/mock URIs are treated as ok (not device-temp files).
 */
export async function checkLocalPhotoUri(
  uri: string | undefined | null,
): Promise<LocalPhotoCheckResult> {
  const trimmed = (uri ?? '').trim();
  if (!trimmed) {
    return { ok: false, reason: 'empty' };
  }
  if (!isLocalDevicePhotoUri(trimmed)) {
    return { ok: true };
  }

  try {
    const info = await FileSystem.getInfoAsync(trimmed);
    if (info.exists) {
      return { ok: true };
    }
    return { ok: false, reason: 'missing' };
  } catch {
    return { ok: false, reason: 'unreachable' };
  }
}

export const PHOTO_REFERENCE_EXPIRED_MESSAGE =
  'Your saved photo is no longer available on this device. Choose a photo again, then continue.';

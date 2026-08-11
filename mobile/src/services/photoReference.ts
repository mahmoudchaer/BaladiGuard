/**
 * Local photo URI reachability for report drafts (#258).
 *
 * Image-picker `file://` URIs may disappear after process restart. Before upload
 * / on draft restore we check the local file exists and clear only the dead
 * photo reference while keeping the rest of the draft.
 */

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
 * Probe whether a local photo URI is still readable.
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
    // Prefer expo-file-system when available (bundled with Expo).
    // Dynamic require keeps unit tests free of native modules when unmocked.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const FileSystem = require('expo-file-system') as {
      getInfoAsync?: (fileUri: string) => Promise<{ exists?: boolean }>;
    };
    if (typeof FileSystem.getInfoAsync === 'function') {
      const info = await FileSystem.getInfoAsync(trimmed);
      if (info?.exists) {
        return { ok: true };
      }
      return { ok: false, reason: 'missing' };
    }
  } catch {
    // fall through to fetch probe
  }

  try {
    const response = await fetch(trimmed);
    if (response.ok) {
      return { ok: true };
    }
    return { ok: false, reason: 'unreachable' };
  } catch {
    return { ok: false, reason: 'unreachable' };
  }
}

export const PHOTO_REFERENCE_EXPIRED_MESSAGE =
  'Your saved photo is no longer available on this device. Choose a photo again, then continue.';

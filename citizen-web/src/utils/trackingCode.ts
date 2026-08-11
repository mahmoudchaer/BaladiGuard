/** Citizen tracking-code rules — keep in sync with backend/app/utils/ticket_ids.py */

export const TRACKING_CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
export const TRACKING_CODE_LENGTH = 6;

export function normalizeTrackingCode(trackingCode: string): string {
  return trackingCode.trim().toUpperCase();
}

export function isValidTrackingCode(trackingCode: string): boolean {
  const normalized = normalizeTrackingCode(trackingCode);
  if (normalized.length !== TRACKING_CODE_LENGTH) {
    return false;
  }
  return [...normalized].every((character) => TRACKING_CODE_ALPHABET.includes(character));
}

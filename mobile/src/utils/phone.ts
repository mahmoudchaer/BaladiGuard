/**
 * Client-side phone validation aligned with backend normalize_phone messages
 * (docs/MVP_API_CONTRACT.md / backend app/utils/phone.py).
 *
 * Full libphonenumber validity is enforced by the API; this layer rejects
 * obviously invalid shapes and requires region for national-format input.
 */

export const PHONE_REQUIRED_MESSAGE = 'Phone number is required.';
export const REGION_REQUIRED_MESSAGE = 'National-format phone numbers require an explicit region.';
export const REGION_INVALID_MESSAGE = 'Region must be an ISO 3166-1 alpha-2 code.';
export const PHONE_PARSE_MESSAGE = 'Phone number could not be parsed.';
export const PHONE_INVALID_MESSAGE = 'Phone number is not a valid number.';
export const PHONE_E164_MESSAGE = 'Phone number is not a valid E.164 value.';

const E164_PATTERN = /^\+[1-9]\d{7,14}$/;
const DIGITS_ONLY = /^\d+$/;

export type PhoneValidationResult =
  { ok: true; phone: string; region?: string } | { ok: false; message: string };

export function normalizeRegion(region: string | null | undefined): string | undefined {
  if (region == null) {
    return undefined;
  }
  const trimmed = region.trim().toUpperCase();
  if (!trimmed) {
    return undefined;
  }
  return trimmed;
}

export function isValidRegionCode(region: string | undefined): boolean {
  return Boolean(region && region.length === 2 && /^[A-Z]{2}$/.test(region));
}

/**
 * Validate and lightly normalize phone input before OTP request.
 * Returns the trimmed phone and optional uppercase region for the API payload.
 */
export function validatePhoneInput(phone: string, region?: string | null): PhoneValidationResult {
  const raw = phone?.trim() ?? '';
  if (!raw) {
    return { ok: false, message: PHONE_REQUIRED_MESSAGE };
  }

  const regionCode = normalizeRegion(region);
  if (regionCode !== undefined && !isValidRegionCode(regionCode)) {
    return { ok: false, message: REGION_INVALID_MESSAGE };
  }

  if (raw.startsWith('+')) {
    const compact = `+${raw.slice(1).replace(/[\s()-]/g, '')}`;
    if (!DIGITS_ONLY.test(compact.slice(1))) {
      return { ok: false, message: PHONE_PARSE_MESSAGE };
    }
    if (!E164_PATTERN.test(compact)) {
      return { ok: false, message: PHONE_E164_MESSAGE };
    }
    return { ok: true, phone: compact, region: regionCode };
  }

  if (!regionCode) {
    return { ok: false, message: REGION_REQUIRED_MESSAGE };
  }

  const nationalDigits = raw.replace(/[\s()-]/g, '');
  if (
    !DIGITS_ONLY.test(nationalDigits) ||
    nationalDigits.length < 6 ||
    nationalDigits.length > 15
  ) {
    return { ok: false, message: PHONE_INVALID_MESSAGE };
  }

  return { ok: true, phone: nationalDigits, region: regionCode };
}

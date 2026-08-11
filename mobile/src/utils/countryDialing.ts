/**
 * Country dialing-code metadata for citizen phone entry (#268).
 *
 * ISO regions and calling codes come from libphonenumber-js (Google
 * libphonenumber metadata). Display names use Intl.DisplayNames so localization
 * can later swap locales (#259) without a second hand-maintained country list.
 * Dialing codes alone never identify a country: US and CA both use +1.
 */

import { getCountries, getCountryCallingCode, type CountryCode } from 'libphonenumber-js';

export type CountryDialingOption = {
  /** ISO 3166-1 alpha-2 region code submitted to OTP APIs. */
  region: string;
  /** International dialing code digits without '+' (e.g. "961"). */
  callingCode: string;
  /** Localized human-readable country name. */
  name: string;
  /** Menu / trigger label, e.g. "Lebanon (+961)". */
  label: string;
};

const ENGLISH_LOCALE = 'en';

function createRegionDisplayNames(locale: string): Intl.DisplayNames | null {
  try {
    return new Intl.DisplayNames([locale], { type: 'region' });
  } catch {
    return null;
  }
}

/**
 * Localized country name with consistent English fallback when a translation
 * is missing or the locale is unsupported.
 */
export function getCountryDisplayName(region: string, locale: string = ENGLISH_LOCALE): string {
  const code = region.trim().toUpperCase();
  if (!code) {
    return '';
  }

  for (const candidate of [locale, ENGLISH_LOCALE]) {
    const displayNames = createRegionDisplayNames(candidate);
    if (!displayNames) {
      continue;
    }
    try {
      const name = displayNames.of(code);
      if (name && name !== code) {
        return name;
      }
    } catch {
      // try next locale
    }
  }

  return code;
}

export function formatCountryDialingLabel(name: string, callingCode: string): string {
  return `${name} (+${callingCode})`;
}

/**
 * Build the full selector catalog sorted alphabetically by the currently
 * displayed country name (not by ISO code or dialing prefix).
 */
export function listCountryDialingOptions(locale: string = ENGLISH_LOCALE): CountryDialingOption[] {
  const countries = getCountries() as CountryCode[];
  const options: CountryDialingOption[] = countries.map((region) => {
    const callingCode = getCountryCallingCode(region);
    const name = getCountryDisplayName(region, locale);
    return {
      region,
      callingCode,
      name,
      label: formatCountryDialingLabel(name, callingCode),
    };
  });

  return options.sort((a, b) => a.name.localeCompare(b.name, locale, { sensitivity: 'base' }));
}

export function findCountryDialingOption(
  region: string | null | undefined,
  locale: string = ENGLISH_LOCALE,
  catalog?: CountryDialingOption[],
): CountryDialingOption | undefined {
  const code = region?.trim().toUpperCase();
  if (!code) {
    return undefined;
  }
  const options = catalog ?? listCountryDialingOptions(locale);
  return options.find((option) => option.region === code);
}

/**
 * Fast filter for country name, ISO alpha-2 code, and dialing code
 * (with or without a leading '+').
 */
export function filterCountryDialingOptions(
  options: CountryDialingOption[],
  query: string,
): CountryDialingOption[] {
  const raw = query.trim().toLowerCase();
  if (!raw) {
    return options;
  }

  const digits = raw.replace(/[^\d]/g, '');
  const withoutPlus = raw.startsWith('+') ? raw.slice(1) : raw;

  return options.filter((option) => {
    if (option.name.toLowerCase().includes(raw)) {
      return true;
    }
    if (option.region.toLowerCase().includes(raw)) {
      return true;
    }
    if (option.label.toLowerCase().includes(raw)) {
      return true;
    }
    if (withoutPlus && option.callingCode.startsWith(withoutPlus.replace(/[^\d]/g, ''))) {
      return true;
    }
    if (digits && option.callingCode.includes(digits)) {
      return true;
    }
    return false;
  });
}

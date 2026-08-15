import { afterEach, describe, expect, it } from 'vitest';

import { getLocale, isRtlLocale, parseAppLocale, resetLocaleForTests, setLocale, t } from '@/i18n';

afterEach(() => {
  resetLocaleForTests();
});

describe('citizen-web i18n', () => {
  it('allowlists locales and defaults to English', () => {
    expect(parseAppLocale('fr')).toBe('fr');
    expect(parseAppLocale('xx')).toBe('en');
    expect(getLocale()).toBe('en');
    expect(t('track.title')).toBe('Track a report');
  });

  it('covers OTP, tracking, and error copy in all locales', () => {
    for (const locale of ['en', 'ar', 'fr'] as const) {
      setLocale(locale);
      expect(t('auth.verify').length).toBeGreaterThan(0);
      expect(t('common.lookUp').length).toBeGreaterThan(0);
      expect(t('errors.generic').length).toBeGreaterThan(0);
      expect(isRtlLocale()).toBe(locale === 'ar');
    }
  });
});

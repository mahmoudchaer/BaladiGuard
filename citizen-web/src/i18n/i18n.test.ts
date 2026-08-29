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

  it('translates full report, profile, and public workflow keys', () => {
    const keys = [
      'report.describe',
      'report.submit',
      'profile.saveChanges',
      'history.askFixed',
      'public.search',
      'track.timeline',
    ];
    const english = keys.map((key) => t(key));
    setLocale('ar');
    keys.forEach((key, index) => {
      expect(t(key)).not.toBe(english[index]);
    });
    setLocale('fr');
    keys.forEach((key, index) => {
      expect(t(key)).not.toBe(english[index]);
    });
  });

  it('covers OTP, tracking, and error copy in all locales', () => {
    for (const locale of ['en', 'ar', 'fr'] as const) {
      setLocale(locale);
      expect(t('auth.verify').length).toBeGreaterThan(0);
      expect(t('common.lookUp').length).toBeGreaterThan(0);
      expect(t('track.invalid').length).toBeGreaterThan(0);
      expect(t('errors.generic').length).toBeGreaterThan(0);
      expect(t('a11y.skipToContent').length).toBeGreaterThan(0);
      expect(t('statusMeaning.IN_PROGRESS').length).toBeGreaterThan(0);
      expect(t('nextAction.RESOLVED').length).toBeGreaterThan(0);
      expect(isRtlLocale()).toBe(locale === 'ar');
    }
  });
});

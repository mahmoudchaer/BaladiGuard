import { afterEach, describe, expect, it } from 'vitest';

import { getLocale, isRtlLocale, parseAppLocale, resetLocaleForTests, setLocale, t } from '@/i18n';

afterEach(() => {
  resetLocaleForTests();
});

describe('i18n locale allowlist', () => {
  it.each([
    ['en', 'en'],
    ['ar', 'ar'],
    ['fr', 'fr'],
    ['zh', 'en'],
    ['EN', 'en'],
    ['<script>', 'en'],
    [null, 'en'],
    [undefined, 'en'],
    ['', 'en'],
  ] as const)('parseAppLocale(%j) is %s', (input, expected) => {
    expect(parseAppLocale(input)).toBe(expected);
  });
});

describe('i18n translations', () => {
  it('returns English product copy by default', () => {
    expect(getLocale()).toBe('en');
    expect(t('auth.verify')).toBe('Verify code');
    expect(t('status.UNDER_REVIEW')).toBe('Under Review');
  });

  it('switches Arabic and French product copy', () => {
    setLocale('ar');
    expect(t('auth.verify')).toBe('تحقق من الرمز');
    expect(isRtlLocale()).toBe(true);

    setLocale('fr');
    expect(t('auth.verify')).toBe('Vérifier le code');
    expect(isRtlLocale()).toBe(false);
  });

  it('falls back to English when a key is missing in the active locale', () => {
    setLocale('ar');
    expect(t('this.key.does.not.exist')).toBe('this.key.does.not.exist');
    expect(t('common.signIn')).toBe('تسجيل الدخول');
  });

  it('interpolates placeholders', () => {
    expect(t('a11y.statusWithLabel', { status: 'Submitted' })).toBe('Status: Submitted');
    setLocale('ar');
    expect(t('a11y.statusWithLabel', { status: 'مُقدَّم' })).toBe('الحالة: مُقدَّم');
  });
});

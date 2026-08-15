import { afterEach, describe, expect, it } from 'vitest';

import { isRtlLocale, parseAppLocale, resetLocaleForTests, setLocale, t } from '@/i18n';

afterEach(() => {
  resetLocaleForTests();
});

describe('admin i18n', () => {
  it('rejects unsafe locale values', () => {
    expect(parseAppLocale('ar')).toBe('ar');
    expect(parseAppLocale('fr')).toBe('fr');
    expect(parseAppLocale('zh-CN')).toBe('en');
    expect(parseAppLocale('javascript:alert(1)')).toBe('en');
  });

  it('translates staff chrome and falls back to English', () => {
    expect(t('login.title')).toBe('BaladiGuard staff login');
    setLocale('ar');
    expect(isRtlLocale()).toBe(true);
    expect(t('login.submit')).toBe('تسجيل الدخول');
    expect(t('missing.key')).toBe('missing.key');
    setLocale('fr');
    expect(t('redaction.approve')).toBe('Approuver le dérivé public');
  });

  it('keeps status meaning independent of color tokens', () => {
    expect(t('status.UNDER_REVIEW')).toBe('Under Review');
    expect(t('priority.critical')).toBe('Critical');
    setLocale('ar');
    expect(t('a11y.statusWithLabel', { status: t('status.UNDER_REVIEW') })).toContain(
      t('status.UNDER_REVIEW'),
    );
  });
});

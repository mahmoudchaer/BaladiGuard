import { describe, expect, it } from 'vitest';

import { buildLoginHref, sanitizeReturnTo } from '@/auth/returnTo';

describe('returnTo helpers', () => {
  it('sanitizes intended return paths', () => {
    expect(sanitizeReturnTo('/report')).toBe('/report');
    expect(sanitizeReturnTo(encodeURIComponent('/track'))).toBe('/track');
    expect(sanitizeReturnTo('https://evil.example')).toBe('/');
    expect(sanitizeReturnTo('//evil.example')).toBe('/');
    expect(sanitizeReturnTo('/profile')).toBe('/profile');
    expect(sanitizeReturnTo('/history')).toBe('/history');
    expect(sanitizeReturnTo('/t/AB23CD')).toBe('/t/AB23CD');
    expect(sanitizeReturnTo('/t/ab23cd')).toBe('/t/ab23cd');
    expect(sanitizeReturnTo('/t/../admin')).toBe('/');
    expect(sanitizeReturnTo('/ticket/tkt_1')).toBe('/');
  });

  it('builds login hrefs with returnTo', () => {
    expect(buildLoginHref('/')).toBe('/login');
    expect(buildLoginHref('/report')).toBe('/login?returnTo=%2Freport');
    expect(buildLoginHref('/profile')).toBe('/login?returnTo=%2Fprofile');
    expect(buildLoginHref('/history')).toBe('/login?returnTo=%2Fhistory');
    expect(buildLoginHref('/t/AB23CD')).toBe('/login?returnTo=%2Ft%2FAB23CD');
  });
});

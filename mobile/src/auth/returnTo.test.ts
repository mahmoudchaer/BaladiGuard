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
  });

  it('builds login hrefs with returnTo', () => {
    expect(buildLoginHref('/')).toBe('/login');
    expect(buildLoginHref('/report')).toBe('/login?returnTo=%2Freport');
    expect(buildLoginHref('/profile')).toBe('/login?returnTo=%2Fprofile');
    expect(buildLoginHref('/history')).toBe('/login?returnTo=%2Fhistory');
  });
});

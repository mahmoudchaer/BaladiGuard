import { describe, expect, it } from 'vitest';

import { buildLoginHref, sanitizeReturnTo } from '@/auth/returnTo';

describe('returnTo helpers', () => {
  it('sanitizes intended return paths', () => {
    expect(sanitizeReturnTo('/report')).toBe('/report');
    expect(sanitizeReturnTo(encodeURIComponent('/track'))).toBe('/track');
    expect(sanitizeReturnTo('https://evil.example')).toBe('/');
    expect(sanitizeReturnTo('//evil.example')).toBe('/');
    expect(sanitizeReturnTo('/profile')).toBe('/');
  });

  it('builds login hrefs with returnTo', () => {
    expect(buildLoginHref('/')).toBe('/login');
    expect(buildLoginHref('/report')).toBe('/login?returnTo=%2Freport');
  });
});

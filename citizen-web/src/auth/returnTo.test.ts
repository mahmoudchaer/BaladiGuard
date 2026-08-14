import { describe, expect, it } from 'vitest';
import { loginPath, sanitizeReturnTo } from '@/auth/returnTo';

describe('citizen return routes', () => {
  it('preserves an internal intended route', () => {
    expect(sanitizeReturnTo('/report?draft=1')).toBe('/report?draft=1');
    expect(loginPath('/history')).toBe('/login?returnTo=%2Fhistory');
  });

  it('rejects external, protocol-relative, and login loops', () => {
    expect(sanitizeReturnTo('https://evil.example')).toBe('/');
    expect(sanitizeReturnTo('//evil.example/path')).toBe('/');
    expect(sanitizeReturnTo('/login?returnTo=/login')).toBe('/');
  });
});

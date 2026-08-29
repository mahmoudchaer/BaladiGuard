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

  it('allows notification deep links and rejects traversal', () => {
    expect(sanitizeReturnTo('/t/ABC234')).toBe('/t/ABC234');
    expect(sanitizeReturnTo('/t/ab23cd')).toBe('/t/ab23cd');
    expect(sanitizeReturnTo('/t/../admin')).toBe('/');
    expect(sanitizeReturnTo('/ticket/tkt_1')).toBe('/');
    expect(loginPath('/t/ABC234')).toBe('/login?returnTo=%2Ft%2FABC234');
  });
});

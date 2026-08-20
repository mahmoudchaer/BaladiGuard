import { describe, expect, it } from 'vitest';
import { resolveMobileConfig } from '@/services/config';

const deployed = (overrides: Record<string, string | undefined> = {}) => ({
  EXPO_PUBLIC_APP_ENV: 'production',
  EXPO_PUBLIC_API_BASE_URL: 'https://api.baladiguard.gov.lb/v1',
  EXPO_PUBLIC_ENABLE_MOCK_API: 'false',
  ...overrides,
});

describe('resolveMobileConfig', () => {
  it('allows explicit mock mode only for local development', () => {
    expect(resolveMobileConfig({ EXPO_PUBLIC_ENABLE_MOCK_API: 'true' }).enableMockApi).toBe(true);
  });

  it('rejects an unlabeled release build instead of selecting local mode', () => {
    expect(() =>
      resolveMobileConfig(
        { EXPO_PUBLIC_ENABLE_MOCK_API: 'true' },
        { citizenAppLinkHost: 'citizen.baladiguard.gov.lb', releaseBuild: true },
      ),
    ).toThrow('EXPO_PUBLIC_APP_ENV must be explicitly set');
  });

  it('rejects mock API mode in production', () => {
    expect(() =>
      resolveMobileConfig(deployed({ EXPO_PUBLIC_ENABLE_MOCK_API: 'true' }), {
        citizenAppLinkHost: 'citizen.baladiguard.gov.lb',
      }),
    ).toThrow('EXPO_PUBLIC_ENABLE_MOCK_API');
  });

  it.each([
    '',
    'http://api.baladiguard.gov.lb/v1',
    'https://localhost:8000/v1',
    'https://[::1]:8000/v1',
    'https://user:password@api.baladiguard.gov.lb/v1',
  ])('rejects unsafe deployed API URL %s', (url) => {
    expect(() =>
      resolveMobileConfig(deployed({ EXPO_PUBLIC_API_BASE_URL: url }), {
        citizenAppLinkHost: 'citizen.baladiguard.gov.lb',
      }),
    ).toThrow();
  });

  it('rejects the placeholder deep-link host in staging', () => {
    expect(() =>
      resolveMobileConfig(deployed({ EXPO_PUBLIC_APP_ENV: 'staging' }), {
        citizenAppLinkHost: 'app.baladiguard.example',
      }),
    ).toThrow('EXPO_PUBLIC_CITIZEN_APP_HOST');
  });

  it.each(['citizen.example.test', 'citizen.example.com'])(
    'rejects reserved example host %s in staging',
    (host) => {
      expect(() =>
        resolveMobileConfig(deployed({ EXPO_PUBLIC_APP_ENV: 'staging' }), {
          citizenAppLinkHost: host,
        }),
      ).toThrow('EXPO_PUBLIC_CITIZEN_APP_HOST');
    },
  );

  it('accepts a real deployed configuration', () => {
    const config = resolveMobileConfig(deployed(), {
      citizenAppLinkHost: 'citizen.baladiguard.gov.lb',
    });
    expect(config.enableMockApi).toBe(false);
    expect(config.apiBaseUrl).toBe('https://api.baladiguard.gov.lb/v1');
  });
});

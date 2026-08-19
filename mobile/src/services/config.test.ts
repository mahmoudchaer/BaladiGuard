import { describe, expect, it } from 'vitest';
import { resolveMobileConfig } from '@/services/config';

const deployed = (overrides: Record<string, string | undefined> = {}) => ({
  EXPO_PUBLIC_APP_ENV: 'production',
  EXPO_PUBLIC_API_BASE_URL: 'https://api.example.test/v1',
  EXPO_PUBLIC_ENABLE_MOCK_API: 'false',
  ...overrides,
});

describe('resolveMobileConfig', () => {
  it('allows explicit mock mode only for local development', () => {
    expect(resolveMobileConfig({ EXPO_PUBLIC_ENABLE_MOCK_API: 'true' }).enableMockApi).toBe(true);
  });

  it('rejects mock API mode in production', () => {
    expect(() =>
      resolveMobileConfig(deployed({ EXPO_PUBLIC_ENABLE_MOCK_API: 'true' }), {
        citizenAppLinkHost: 'citizen.example.test',
      }),
    ).toThrow('EXPO_PUBLIC_ENABLE_MOCK_API');
  });

  it.each([
    '',
    'http://api.example.test/v1',
    'https://localhost:8000/v1',
    'https://[::1]:8000/v1',
    'https://user:password@api.example.test/v1',
  ])('rejects unsafe deployed API URL %s', (url) => {
    expect(() =>
      resolveMobileConfig(deployed({ EXPO_PUBLIC_API_BASE_URL: url }), {
        citizenAppLinkHost: 'citizen.example.test',
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

  it('accepts a real deployed configuration', () => {
    const config = resolveMobileConfig(deployed(), {
      citizenAppLinkHost: 'citizen.example.test',
    });
    expect(config.enableMockApi).toBe(false);
    expect(config.apiBaseUrl).toBe('https://api.example.test/v1');
  });
});

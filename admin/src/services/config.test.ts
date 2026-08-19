import { describe, expect, it } from 'vitest';
import { resolveAdminConfig } from '@/services/config';

const deployed = (overrides: Partial<ImportMetaEnv> = {}) => ({
  VITE_APP_ENV: 'production',
  VITE_API_BASE_URL: 'https://api.example.test',
  VITE_USE_MOCK_DATA: 'false',
  ...overrides,
});

describe('resolveAdminConfig', () => {
  it('keeps explicit local mock mode available', () => {
    const config = resolveAdminConfig({ VITE_APP_ENV: 'local', VITE_USE_MOCK_DATA: 'true' });
    expect(config.useMockData).toBe(true);
    expect(config.apiBaseUrl).toBe('http://localhost:8000');
  });

  it.each(['staging', 'production'])('rejects mock mode in %s', (appEnv) => {
    expect(() =>
      resolveAdminConfig(deployed({ VITE_APP_ENV: appEnv, VITE_USE_MOCK_DATA: 'true' })),
    ).toThrow('VITE_USE_MOCK_DATA');
  });

  it.each([
    '',
    'http://api.example.test',
    'https://localhost:8000',
    'https://[::1]:8000',
    'https://user:password@api.example.test',
  ])('rejects unsafe deployed API origin %s', (apiBaseUrl) => {
    expect(() => resolveAdminConfig(deployed({ VITE_API_BASE_URL: apiBaseUrl }))).toThrow();
  });

  it('rejects browser-bundled staff credentials in production', () => {
    expect(() => resolveAdminConfig(deployed({ VITE_STAFF_PASSWORD: 'anything' }))).toThrow(
      'local mock settings only',
    );
  });

  it('accepts a credential-free HTTPS production configuration', () => {
    const config = resolveAdminConfig(deployed({ VITE_API_BASE_URL: 'https://api.example.test/' }));
    expect(config.apiBaseUrl).toBe('https://api.example.test');
    expect(config.useMockData).toBe(false);
  });
});

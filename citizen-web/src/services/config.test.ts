import { describe, expect, it } from 'vitest';
import { resolveCitizenWebConfig } from '@/services/config';

describe('resolveCitizenWebConfig', () => {
  it('defaults local API to localhost when unset', () => {
    const config = resolveCitizenWebConfig({
      VITE_APP_ENV: 'local',
      VITE_API_BASE_URL: undefined,
      VITE_USE_MOCK_DATA: undefined,
    });
    expect(config.apiBaseUrl).toBe('http://localhost:8000');
    expect(config.useMockData).toBe(false);
  });

  it('allows mock data only outside staging/production', () => {
    const config = resolveCitizenWebConfig({
      VITE_APP_ENV: 'development',
      VITE_API_BASE_URL: 'http://localhost:8000',
      VITE_USE_MOCK_DATA: 'true',
    });
    expect(config.useMockData).toBe(true);
  });

  it('rejects mock data in production', () => {
    expect(() =>
      resolveCitizenWebConfig({
        VITE_APP_ENV: 'production',
        VITE_API_BASE_URL: 'https://api.example.com',
        VITE_USE_MOCK_DATA: 'true',
      }),
    ).toThrow(/Mock data is local\/dev only/);
  });

  it('requires https non-localhost API in staging', () => {
    expect(() =>
      resolveCitizenWebConfig({
        VITE_APP_ENV: 'staging',
        VITE_API_BASE_URL: undefined,
        VITE_USE_MOCK_DATA: undefined,
      }),
    ).toThrow(/required/);

    expect(() =>
      resolveCitizenWebConfig({
        VITE_APP_ENV: 'staging',
        VITE_API_BASE_URL: 'http://api.example.com',
        VITE_USE_MOCK_DATA: undefined,
      }),
    ).toThrow(/https/);

    expect(() =>
      resolveCitizenWebConfig({
        VITE_APP_ENV: 'staging',
        VITE_API_BASE_URL: 'https://localhost:8000',
        VITE_USE_MOCK_DATA: undefined,
      }),
    ).toThrow(/localhost/);
  });

  it('accepts validated production config', () => {
    const config = resolveCitizenWebConfig({
      VITE_APP_ENV: 'production',
      VITE_API_BASE_URL: 'https://api.baladiguard.example/',
      VITE_USE_MOCK_DATA: 'false',
    });
    expect(config.apiBaseUrl).toBe('https://api.baladiguard.example');
    expect(config.useMockData).toBe(false);
  });
});

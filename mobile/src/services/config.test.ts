import { afterEach, describe, expect, it } from 'vitest';

import {
  assertMobileRuntimeConfig,
  buildMobileRuntimeConfig,
  buildMobileRuntimeConfigFromValues,
  readExpoPublicEnv,
} from '@/services/config';
import type { MobileRuntimeConfig } from '@/services/config';

function baseConfig(overrides: Partial<MobileRuntimeConfig> = {}): MobileRuntimeConfig {
  return {
    apiBaseUrl: 'http://localhost:8000/v1',
    enableMockApi: false,
    appEnv: 'local',
    appVersion: '0.1.0',
    privacyPolicyUrl: 'https://example.gov/privacy',
    isReleaseBinary: false,
    ...overrides,
  };
}

describe('assertMobileRuntimeConfig', () => {
  it('allows local development with mock mode and localhost HTTP', () => {
    expect(() =>
      assertMobileRuntimeConfig(
        baseConfig({
          enableMockApi: true,
          apiBaseUrl: 'http://localhost:8000/v1',
          appEnv: 'local',
          isReleaseBinary: false,
        }),
      ),
    ).not.toThrow();
  });

  it('rejects mock mode when APP_ENV is production', () => {
    expect(() =>
      assertMobileRuntimeConfig(
        baseConfig({
          appEnv: 'production',
          enableMockApi: true,
          apiBaseUrl: 'https://api.example.gov/v1',
        }),
      ),
    ).toThrow(/cannot enable EXPO_PUBLIC_ENABLE_MOCK_API/);
  });

  it('rejects mock mode for release binaries even when APP_ENV is preview', () => {
    expect(() =>
      assertMobileRuntimeConfig(
        baseConfig({
          appEnv: 'preview',
          enableMockApi: true,
          apiBaseUrl: 'https://api.example.gov/v1',
          isReleaseBinary: true,
        }),
      ),
    ).toThrow(/cannot enable EXPO_PUBLIC_ENABLE_MOCK_API/);
  });

  it('rejects non-HTTPS API URLs in production', () => {
    expect(() =>
      assertMobileRuntimeConfig(
        baseConfig({
          appEnv: 'production',
          apiBaseUrl: 'http://api.example.gov/v1',
        }),
      ),
    ).toThrow(/require an HTTPS/);
  });

  it('rejects localhost API URLs in production', () => {
    expect(() =>
      assertMobileRuntimeConfig(
        baseConfig({
          appEnv: 'production',
          apiBaseUrl: 'https://localhost:8000/v1',
        }),
      ),
    ).toThrow(/localhost\/loopback/);
  });

  it('rejects empty API URLs in release binaries', () => {
    expect(() =>
      assertMobileRuntimeConfig(
        baseConfig({
          appEnv: 'preview',
          apiBaseUrl: '   ',
          isReleaseBinary: true,
        }),
      ),
    ).toThrow(/require EXPO_PUBLIC_API_BASE_URL/);
  });

  it('accepts a production HTTPS API URL with mock disabled', () => {
    expect(() =>
      assertMobileRuntimeConfig(
        baseConfig({
          appEnv: 'production',
          enableMockApi: false,
          apiBaseUrl: 'https://api.baladiguard.example/v1',
          isReleaseBinary: true,
        }),
      ),
    ).not.toThrow();
  });
});

describe('buildMobileRuntimeConfig', () => {
  const originalEnv = { ...process.env };

  afterEach(() => {
    process.env = { ...originalEnv };
  });

  it('builds a local config from environment defaults without throwing', () => {
    delete process.env.EXPO_PUBLIC_API_BASE_URL;
    delete process.env.EXPO_PUBLIC_ENABLE_MOCK_API;
    delete process.env.EXPO_PUBLIC_APP_ENV;

    const config = buildMobileRuntimeConfig({ env: process.env, isReleaseBinary: false });
    expect(config.appEnv).toBe('local');
    expect(config.enableMockApi).toBe(false);
    // Localhost is provided by mobile/.env, not a compiled-in default.
    expect(config.apiBaseUrl).toBe('');
  });

  it('accepts an injected localhost URL for local/dev test fixtures', () => {
    const config = buildMobileRuntimeConfigFromValues({
      apiBaseUrl: 'http://localhost:8000/v1',
      enableMockApi: true,
      appEnv: 'local',
      isReleaseBinary: false,
    });
    expect(config.apiBaseUrl).toContain('localhost');
    expect(config.enableMockApi).toBe(true);
  });

  it('fails closed when production env is misconfigured at build time', () => {
    process.env.EXPO_PUBLIC_APP_ENV = 'production';
    process.env.EXPO_PUBLIC_ENABLE_MOCK_API = 'true';
    process.env.EXPO_PUBLIC_API_BASE_URL = 'https://api.example.gov/v1';

    expect(() => buildMobileRuntimeConfig({ env: process.env, isReleaseBinary: false })).toThrow(
      /cannot enable EXPO_PUBLIC_ENABLE_MOCK_API/,
    );
  });

  it('reads Expo public env through direct process.env member access', () => {
    process.env.EXPO_PUBLIC_API_BASE_URL = 'https://api.inline.example/v1';
    process.env.EXPO_PUBLIC_ENABLE_MOCK_API = 'false';
    process.env.EXPO_PUBLIC_APP_ENV = 'production';

    expect(readExpoPublicEnv()).toEqual({
      apiBaseUrl: 'https://api.inline.example/v1',
      enableMockApi: 'false',
      appEnv: 'production',
      privacyPolicyUrl: process.env.EXPO_PUBLIC_PRIVACY_POLICY_URL,
    });
  });

  it('builds from explicit values without needing an env alias object', () => {
    const config = buildMobileRuntimeConfigFromValues({
      apiBaseUrl: 'https://api.baladiguard.example/v1',
      enableMockApi: false,
      appEnv: 'production',
      isReleaseBinary: true,
    });
    expect(config.apiBaseUrl).toBe('https://api.baladiguard.example/v1');
    expect(config.enableMockApi).toBe(false);
  });
});

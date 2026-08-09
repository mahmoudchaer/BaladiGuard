import Constants from 'expo-constants';

export type MobileRuntimeConfig = {
  apiBaseUrl: string;
  enableMockApi: boolean;
  appEnv: string;
  appVersion: string;
  privacyPolicyUrl: string;
  isReleaseBinary: boolean;
};

// Intentionally no localhost default in this module — production export bundles
// must not embed loopback URLs. Local/dev sets EXPO_PUBLIC_API_BASE_URL via .env
// (see mobile/.env.example). Tests inject values through FromValues.
const DEFAULT_PRIVACY_POLICY_URL =
  'https://github.com/mahmoudchaer/BaladiGuard/blob/main/docs/privacy-lifecycle.md';

function resolveIsReleaseBinary(): boolean {
  // Expo/Metro sets __DEV__=true for local bundling; release/EAS binaries set false.
  if (typeof __DEV__ === 'boolean') {
    return !__DEV__;
  }
  return false;
}

function isProductionEnv(appEnv: string): boolean {
  const normalized = appEnv.trim().toLowerCase();
  return normalized === 'production' || normalized === 'prod';
}

function isLoopbackOrLocalHost(hostname: string): boolean {
  const host = hostname.trim().toLowerCase();
  return (
    host === 'localhost' ||
    host === '127.0.0.1' ||
    host === '::1' ||
    host === '0.0.0.0' ||
    host.endsWith('.local')
  );
}

/**
 * Fail closed for production/release binaries so mock mode or a local API URL
 * cannot ship (issue #192). Local/dev Expo sessions remain unrestricted.
 */
export function assertMobileRuntimeConfig(config: MobileRuntimeConfig): void {
  const enforceHardening = isProductionEnv(config.appEnv) || config.isReleaseBinary;
  if (!enforceHardening) {
    return;
  }

  if (config.enableMockApi) {
    throw new Error(
      'BaladiGuard release/production builds cannot enable EXPO_PUBLIC_ENABLE_MOCK_API.',
    );
  }

  const apiBaseUrl = config.apiBaseUrl.trim();
  if (!apiBaseUrl) {
    throw new Error('BaladiGuard release/production builds require EXPO_PUBLIC_API_BASE_URL.');
  }

  let parsed: URL;
  try {
    parsed = new URL(apiBaseUrl);
  } catch {
    throw new Error(
      'EXPO_PUBLIC_API_BASE_URL must be an absolute URL (for example https://api.example.gov/v1).',
    );
  }

  if (parsed.protocol !== 'https:') {
    throw new Error(
      'BaladiGuard release/production builds require an HTTPS EXPO_PUBLIC_API_BASE_URL.',
    );
  }

  if (isLoopbackOrLocalHost(parsed.hostname)) {
    throw new Error(
      'BaladiGuard release/production builds cannot use a localhost/loopback API base URL.',
    );
  }
}

/**
 * Pure helper for tests / injected values. Prefer {@link readExpoPublicEnv} +
 * {@link buildMobileRuntimeConfig} at runtime so Metro can inline EXPO_PUBLIC_* vars.
 */
export function buildMobileRuntimeConfigFromValues(input: {
  apiBaseUrl?: string | null;
  enableMockApi?: string | boolean | null;
  appEnv?: string | null;
  privacyPolicyUrl?: string | null;
  isReleaseBinary?: boolean;
}): MobileRuntimeConfig {
  const isReleaseBinary = input.isReleaseBinary ?? resolveIsReleaseBinary();
  const extra = (Constants.expoConfig?.extra ?? {}) as {
    privacyPolicyUrl?: string;
  };
  const enableMockRaw = input.enableMockApi;
  const enableMockApi =
    typeof enableMockRaw === 'boolean' ? enableMockRaw : enableMockRaw === 'true';

  const config: MobileRuntimeConfig = {
    apiBaseUrl: (input.apiBaseUrl ?? '').trim(),
    enableMockApi,
    appEnv: (input.appEnv ?? 'local').trim() || 'local',
    appVersion: Constants.expoConfig?.version ?? '0.1.0',
    privacyPolicyUrl: (
      input.privacyPolicyUrl ??
      extra.privacyPolicyUrl ??
      DEFAULT_PRIVACY_POLICY_URL
    ).trim(),
    isReleaseBinary,
  };

  assertMobileRuntimeConfig(config);
  return config;
}

/**
 * Read public Expo env via direct ``process.env.EXPO_PUBLIC_*`` member access.
 * Metro only inlines these literal references — aliases like ``env.EXPO_PUBLIC_*``
 * leave unresolved keys in release bundles (issue #192 review).
 */
export function readExpoPublicEnv(): {
  apiBaseUrl: string | undefined;
  enableMockApi: string | undefined;
  appEnv: string | undefined;
  privacyPolicyUrl: string | undefined;
} {
  return {
    apiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL,
    enableMockApi: process.env.EXPO_PUBLIC_ENABLE_MOCK_API,
    appEnv: process.env.EXPO_PUBLIC_APP_ENV,
    privacyPolicyUrl: process.env.EXPO_PUBLIC_PRIVACY_POLICY_URL,
  };
}

export function buildMobileRuntimeConfig(options?: {
  /** Test-only injection. Production/runtime must omit this so Metro inlines env. */
  env?: NodeJS.ProcessEnv;
  isReleaseBinary?: boolean;
}): MobileRuntimeConfig {
  if (options?.env) {
    return buildMobileRuntimeConfigFromValues({
      apiBaseUrl: options.env.EXPO_PUBLIC_API_BASE_URL,
      enableMockApi: options.env.EXPO_PUBLIC_ENABLE_MOCK_API,
      appEnv: options.env.EXPO_PUBLIC_APP_ENV,
      privacyPolicyUrl: options.env.EXPO_PUBLIC_PRIVACY_POLICY_URL,
      isReleaseBinary: options.isReleaseBinary,
    });
  }

  const publicEnv = readExpoPublicEnv();
  return buildMobileRuntimeConfigFromValues({
    apiBaseUrl: publicEnv.apiBaseUrl,
    enableMockApi: publicEnv.enableMockApi,
    appEnv: publicEnv.appEnv,
    privacyPolicyUrl: publicEnv.privacyPolicyUrl,
    isReleaseBinary: options?.isReleaseBinary,
  });
}

export const appConfig = buildMobileRuntimeConfig();

import Constants from 'expo-constants';

export type MobileRuntimeConfig = {
  apiBaseUrl: string;
  enableMockApi: boolean;
  appEnv: string;
  appVersion: string;
  privacyPolicyUrl: string;
  isReleaseBinary: boolean;
};

const DEFAULT_LOCAL_API = 'http://localhost:8000/v1';
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

export function buildMobileRuntimeConfig(options?: {
  env?: NodeJS.ProcessEnv;
  isReleaseBinary?: boolean;
}): MobileRuntimeConfig {
  const env = options?.env ?? process.env;
  const isReleaseBinary = options?.isReleaseBinary ?? resolveIsReleaseBinary();
  const extra = (Constants.expoConfig?.extra ?? {}) as {
    privacyPolicyUrl?: string;
  };

  const config: MobileRuntimeConfig = {
    apiBaseUrl: (env.EXPO_PUBLIC_API_BASE_URL ?? DEFAULT_LOCAL_API).trim(),
    enableMockApi: env.EXPO_PUBLIC_ENABLE_MOCK_API === 'true',
    appEnv: (env.EXPO_PUBLIC_APP_ENV ?? 'local').trim() || 'local',
    appVersion: Constants.expoConfig?.version ?? '0.1.0',
    privacyPolicyUrl: (
      env.EXPO_PUBLIC_PRIVACY_POLICY_URL ??
      extra.privacyPolicyUrl ??
      DEFAULT_PRIVACY_POLICY_URL
    ).trim(),
    isReleaseBinary,
  };

  assertMobileRuntimeConfig(config);
  return config;
}

export const appConfig = buildMobileRuntimeConfig();

import Constants from 'expo-constants';

export type MobileEnvironment = 'local' | 'development' | 'test' | 'staging' | 'production';

type MobilePublicEnvironment = Record<string, string | undefined>;

function normalizeEnvironment(raw: string | undefined, releaseBuild: boolean): MobileEnvironment {
  if (!raw?.trim() && releaseBuild) {
    throw new Error('EXPO_PUBLIC_APP_ENV must be explicitly set for a release build.');
  }
  const value = (raw ?? 'local').trim().toLowerCase();
  if (value === 'prod' || value === 'prd') return 'production';
  if (value === 'dev' || value === 'develop') return 'development';
  if (['local', 'development', 'test', 'staging', 'production'].includes(value)) {
    return value as MobileEnvironment;
  }
  throw new Error('EXPO_PUBLIC_APP_ENV must be local, development, test, staging, or production.');
}

function isPlaceholderHost(host: string): boolean {
  const normalized = host.trim().toLowerCase();
  return (
    normalized === 'example' ||
    normalized.endsWith('.example') ||
    normalized === 'example.com' ||
    normalized.endsWith('.example.com') ||
    normalized === 'example.test' ||
    normalized.endsWith('.example.test')
  );
}

function validateDeployedApiUrl(raw: string, appEnv: MobileEnvironment): string {
  if (!raw) throw new Error(`EXPO_PUBLIC_API_BASE_URL is required in ${appEnv}.`);
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error('EXPO_PUBLIC_API_BASE_URL must be a valid absolute URL.');
  }
  if (parsed.protocol !== 'https:')
    throw new Error(`The mobile API URL must use HTTPS in ${appEnv}.`);
  if (['localhost', '127.0.0.1', '::1', '[::1]'].includes(parsed.hostname.toLowerCase())) {
    throw new Error(`The mobile API URL must not target localhost in ${appEnv}.`);
  }
  if (parsed.username || parsed.password) {
    throw new Error('EXPO_PUBLIC_API_BASE_URL must not contain embedded credentials.');
  }
  return raw.replace(/\/+$/, '');
}

export function resolveMobileConfig(
  env: MobilePublicEnvironment,
  options: { appVersion?: string; citizenAppLinkHost?: string; releaseBuild?: boolean } = {},
) {
  // __DEV__ is false in a native release bundle. Require an explicit deployed
  // configuration there so a missing label cannot select localhost/mock defaults.
  const releaseBuild = options.releaseBuild ?? (typeof __DEV__ !== 'undefined' && !__DEV__);
  const appEnv = normalizeEnvironment(env.EXPO_PUBLIC_APP_ENV, releaseBuild);
  if (releaseBuild && appEnv !== 'staging' && appEnv !== 'production') {
    throw new Error('EXPO_PUBLIC_APP_ENV must be staging or production for a release build.');
  }
  const deployed = releaseBuild || appEnv === 'staging' || appEnv === 'production';
  const enableMockApi = env.EXPO_PUBLIC_ENABLE_MOCK_API === 'true';
  const rawApiBase = (env.EXPO_PUBLIC_API_BASE_URL ?? '').trim();
  const citizenAppLinkHost = (options.citizenAppLinkHost ?? '').trim();

  if (deployed && enableMockApi) {
    throw new Error(`EXPO_PUBLIC_ENABLE_MOCK_API cannot be true in ${appEnv}.`);
  }
  if (deployed && (!citizenAppLinkHost || isPlaceholderHost(citizenAppLinkHost))) {
    throw new Error(`A real EXPO_PUBLIC_CITIZEN_APP_HOST is required in ${appEnv}.`);
  }
  if (!deployed && !enableMockApi && !rawApiBase) {
    throw new Error(
      'EXPO_PUBLIC_API_BASE_URL is required when the local mock API is disabled. Copy mobile/.env.example to mobile/.env and set it for your device.',
    );
  }

  return {
    apiBaseUrl: deployed
      ? validateDeployedApiUrl(rawApiBase, appEnv)
      : (rawApiBase || 'https://mock.invalid/v1').replace(/\/+$/, ''),
    enableMockApi: deployed ? false : enableMockApi,
    appEnv,
    appVersion: options.appVersion ?? '0.1.0',
    citizenAppLinkHost: citizenAppLinkHost || 'app.baladiguard.example',
  };
}

// Keep direct EXPO_PUBLIC_* member reads so Metro can inline release values.
export const appConfig = resolveMobileConfig(
  {
    EXPO_PUBLIC_API_BASE_URL: process.env.EXPO_PUBLIC_API_BASE_URL,
    EXPO_PUBLIC_ENABLE_MOCK_API:
      process.env.EXPO_PUBLIC_ENABLE_MOCK_API ??
      (process.env.NODE_ENV === 'test' ? 'true' : undefined),
    EXPO_PUBLIC_APP_ENV: process.env.EXPO_PUBLIC_APP_ENV,
  },
  {
    appVersion: Constants.expoConfig?.version,
    citizenAppLinkHost: (Constants.expoConfig?.extra as { citizenAppLinkHost?: string } | undefined)
      ?.citizenAppLinkHost,
  },
);

import Constants from 'expo-constants';

export type MobileEnvironment = 'local' | 'development' | 'test' | 'staging' | 'production';

type MobilePublicEnvironment = Record<string, string | undefined>;

function normalizeEnvironment(raw: string | undefined): MobileEnvironment {
  const value = (raw ?? 'local').trim().toLowerCase();
  if (value === 'prod' || value === 'prd') return 'production';
  if (value === 'dev' || value === 'develop') return 'development';
  if (['local', 'development', 'test', 'staging', 'production'].includes(value)) {
    return value as MobileEnvironment;
  }
  throw new Error('EXPO_PUBLIC_APP_ENV must be local, development, test, staging, or production.');
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
  options: { appVersion?: string; citizenAppLinkHost?: string } = {},
) {
  const appEnv = normalizeEnvironment(env.EXPO_PUBLIC_APP_ENV);
  const deployed = appEnv === 'staging' || appEnv === 'production';
  const enableMockApi = env.EXPO_PUBLIC_ENABLE_MOCK_API === 'true';
  const rawApiBase = (env.EXPO_PUBLIC_API_BASE_URL ?? '').trim();
  const citizenAppLinkHost = (options.citizenAppLinkHost ?? '').trim();

  if (deployed && enableMockApi) {
    throw new Error(`EXPO_PUBLIC_ENABLE_MOCK_API cannot be true in ${appEnv}.`);
  }
  if (deployed && (!citizenAppLinkHost || citizenAppLinkHost.endsWith('.example'))) {
    throw new Error(`A real EXPO_PUBLIC_CITIZEN_APP_HOST is required in ${appEnv}.`);
  }

  return {
    apiBaseUrl: deployed
      ? validateDeployedApiUrl(rawApiBase, appEnv)
      : (rawApiBase || 'http://localhost:8000/v1').replace(/\/+$/, ''),
    enableMockApi: deployed ? false : enableMockApi,
    appEnv,
    appVersion: options.appVersion ?? '0.1.0',
    citizenAppLinkHost: citizenAppLinkHost || 'app.baladiguard.example',
  };
}

export const appConfig = resolveMobileConfig(process.env, {
  appVersion: Constants.expoConfig?.version,
  citizenAppLinkHost: (Constants.expoConfig?.extra as { citizenAppLinkHost?: string } | undefined)
    ?.citizenAppLinkHost,
});

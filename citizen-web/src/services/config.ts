export type AppEnvironment = 'local' | 'development' | 'test' | 'staging' | 'production';

export type CitizenWebConfig = {
  appEnv: AppEnvironment;
  /** API origin without trailing slash (e.g. https://api.example.com). Paths append /v1/... */
  apiBaseUrl: string;
  useMockData: boolean;
};

const LOCAL_DEFAULT_API = 'http://localhost:8000';

function normalizeEnv(raw: string | undefined): AppEnvironment {
  const value = (raw ?? 'local').trim().toLowerCase();
  if (value === 'prod') {
    return 'production';
  }
  if (value === 'dev' || value === 'develop') {
    return 'development';
  }
  if (
    value === 'local' ||
    value === 'development' ||
    value === 'test' ||
    value === 'staging' ||
    value === 'production'
  ) {
    return value;
  }
  throw new Error(
    `Invalid VITE_APP_ENV=${raw ?? ''}. Use local, development, test, staging, or production.`,
  );
}

function isLocalhostUrl(url: string): boolean {
  try {
    const host = new URL(url).hostname.toLowerCase();
    return host === 'localhost' || host === '127.0.0.1' || host === '::1';
  } catch {
    return false;
  }
}

/**
 * Resolve and validate citizen-web configuration.
 * Staging/production never silently fall back to localhost or mock data (#263).
 */
export function resolveCitizenWebConfig(
  env: Pick<
    ImportMetaEnv,
    'VITE_APP_ENV' | 'VITE_API_BASE_URL' | 'VITE_USE_MOCK_DATA'
  > = import.meta.env,
): CitizenWebConfig {
  const appEnv = normalizeEnv(env.VITE_APP_ENV);
  const rawBase = (env.VITE_API_BASE_URL ?? '').trim();
  const useMockData = env.VITE_USE_MOCK_DATA === 'true';
  const isProdLike = appEnv === 'staging' || appEnv === 'production';

  if (isProdLike && useMockData) {
    throw new Error(
      `VITE_USE_MOCK_DATA cannot be true when VITE_APP_ENV=${appEnv}. Mock data is local/dev only.`,
    );
  }

  if (isProdLike) {
    if (!rawBase) {
      throw new Error(
        `VITE_API_BASE_URL is required when VITE_APP_ENV=${appEnv}. Production never defaults to localhost.`,
      );
    }
    let parsed: URL;
    try {
      parsed = new URL(rawBase);
    } catch {
      throw new Error(`VITE_API_BASE_URL is not a valid URL: ${rawBase}`);
    }
    if (parsed.protocol !== 'https:') {
      throw new Error(`VITE_API_BASE_URL must use https in ${appEnv} (got ${parsed.protocol}).`);
    }
    if (isLocalhostUrl(rawBase)) {
      throw new Error(`VITE_API_BASE_URL must not target localhost in ${appEnv}.`);
    }
    return {
      appEnv,
      apiBaseUrl: rawBase.replace(/\/+$/, ''),
      useMockData: false,
    };
  }

  const apiBaseUrl = (rawBase || LOCAL_DEFAULT_API).replace(/\/+$/, '');
  return { appEnv, apiBaseUrl, useMockData };
}

export const config: CitizenWebConfig = resolveCitizenWebConfig();

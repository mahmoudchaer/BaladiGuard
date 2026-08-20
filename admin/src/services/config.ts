export type AppEnvironment = 'local' | 'development' | 'test' | 'staging' | 'production';

const LOCAL_API_BASE_URL = 'http://localhost:8000';

function normalizeEnvironment(raw: string | undefined, productionBuild: boolean): AppEnvironment {
  if (!raw?.trim() && productionBuild) {
    throw new Error('VITE_APP_ENV must be explicitly set for a production Vite build.');
  }
  const value = (raw ?? 'local').trim().toLowerCase();
  if (value === 'prod' || value === 'prd') return 'production';
  if (value === 'dev' || value === 'develop') return 'development';
  if (['local', 'development', 'test', 'staging', 'production'].includes(value)) {
    return value as AppEnvironment;
  }
  throw new Error('VITE_APP_ENV must be local, development, test, staging, or production.');
}

function deployedApiOrigin(raw: string, appEnv: AppEnvironment): string {
  if (!raw) throw new Error(`VITE_API_BASE_URL is required when VITE_APP_ENV=${appEnv}.`);
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error('VITE_API_BASE_URL must be a valid absolute URL.');
  }
  if (parsed.protocol !== 'https:') {
    throw new Error(`VITE_API_BASE_URL must use HTTPS when VITE_APP_ENV=${appEnv}.`);
  }
  if (['localhost', '127.0.0.1', '::1', '[::1]'].includes(parsed.hostname.toLowerCase())) {
    throw new Error(`VITE_API_BASE_URL must not target localhost when VITE_APP_ENV=${appEnv}.`);
  }
  if (parsed.username || parsed.password) {
    throw new Error('VITE_API_BASE_URL must not contain embedded credentials.');
  }
  return raw.replace(/\/+$/, '');
}

type AdminPublicEnvironment = Partial<
  Pick<
    ImportMetaEnv,
    | 'VITE_APP_ENV'
    | 'VITE_API_BASE_URL'
    | 'VITE_USE_MOCK_DATA'
    | 'VITE_STAFF_USERNAME'
    | 'VITE_STAFF_PASSWORD'
    | 'PROD'
  >
>;

export function resolveAdminConfig(env: AdminPublicEnvironment = import.meta.env) {
  // Vite replaces PROD at build time. Do not let an omitted public app label turn
  // a browser production artifact into a local/mock build.
  const productionBuild = import.meta.env.PROD || env.PROD === true;
  const appEnv = normalizeEnvironment(env.VITE_APP_ENV, productionBuild);
  if (productionBuild && appEnv !== 'staging' && appEnv !== 'production') {
    throw new Error('VITE_APP_ENV must be staging or production for a production Vite build.');
  }
  const deployed = productionBuild || appEnv === 'staging' || appEnv === 'production';
  const useMockData = env.VITE_USE_MOCK_DATA === 'true';
  const rawApiBase = (env.VITE_API_BASE_URL ?? '').trim();

  if (deployed && useMockData) {
    throw new Error(`VITE_USE_MOCK_DATA cannot be true when VITE_APP_ENV=${appEnv}.`);
  }
  if (deployed && (env.VITE_STAFF_USERNAME || env.VITE_STAFF_PASSWORD)) {
    throw new Error('VITE_STAFF_USERNAME and VITE_STAFF_PASSWORD are local mock settings only.');
  }

  return {
    appEnv,
    apiBaseUrl: deployed
      ? deployedApiOrigin(rawApiBase, appEnv)
      : (rawApiBase || LOCAL_API_BASE_URL).replace(/\/+$/, ''),
    useMockData: deployed ? false : useMockData,
    staffAuth: {
      username: env.VITE_STAFF_USERNAME ?? '',
      password: env.VITE_STAFF_PASSWORD ?? '',
    },
  };
}

export const config = resolveAdminConfig();

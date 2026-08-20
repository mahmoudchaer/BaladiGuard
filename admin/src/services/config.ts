const DEFAULT_API_BASE_URL = 'http://localhost:8000';
const DEFAULT_STAFF_USERNAME = 'staff';
const DEFAULT_STAFF_PASSWORD = 'staff-demo-password';

// Fail closed (#312): local-development defaults are only compiled into the
// bundle when VITE_APP_ENV is unset/local. Staging and production builds must
// provide explicit values; the minifier dead-code-eliminates the defaults.
const appEnv = import.meta.env.VITE_APP_ENV ?? 'local';
const isLocal = appEnv === 'local';

export const config = {
  appEnv,
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? (isLocal ? DEFAULT_API_BASE_URL : ''),
  useMockData: import.meta.env.VITE_USE_MOCK_DATA === 'true',
  staffAuth: {
    username: import.meta.env.VITE_STAFF_USERNAME ?? (isLocal ? DEFAULT_STAFF_USERNAME : ''),
    password: import.meta.env.VITE_STAFF_PASSWORD ?? (isLocal ? DEFAULT_STAFF_PASSWORD : ''),
  },
};

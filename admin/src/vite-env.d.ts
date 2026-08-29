/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_APP_ENV?: string;
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_USE_MOCK_DATA?: string;
  readonly VITE_CITIZEN_WEB_URL?: string;
  readonly VITE_STAFF_USERNAME?: string;
  readonly VITE_STAFF_PASSWORD?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

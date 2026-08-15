import { defineConfig, devices } from '@playwright/test';

const apiOrigin = 'http://127.0.0.1:18080';
const spaOrigin = 'http://127.0.0.1:4174';

export default defineConfig({
  testDir: './e2e-browser',
  testMatch: '**/*.spec.ts',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: spaOrigin,
    trace: 'on-first-retry',
  },
  webServer: [
    {
      command: 'node e2e-browser/mock-api.mjs',
      url: `${apiOrigin}/health`,
      reuseExistingServer: false,
      env: {
        ...process.env,
        CITIZEN_WEB_E2E_API_PORT: '18080',
        CITIZEN_WEB_E2E_ORIGIN: spaOrigin,
      },
    },
    {
      command: 'npm run build && npm run preview -- --host 127.0.0.1 --port 4174 --strictPort',
      url: spaOrigin,
      reuseExistingServer: false,
      env: {
        ...process.env,
        VITE_APP_ENV: 'local',
        VITE_API_BASE_URL: apiOrigin,
        VITE_USE_MOCK_DATA: 'false',
      },
    },
  ],
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});

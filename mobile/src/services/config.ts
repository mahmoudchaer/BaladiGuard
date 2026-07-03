import Constants from 'expo-constants';

export const appConfig = {
  apiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000/v1',
  enableMockApi: (process.env.EXPO_PUBLIC_ENABLE_MOCK_API ?? 'true') === 'true',
  appEnv: process.env.EXPO_PUBLIC_APP_ENV ?? 'local',
  appVersion: Constants.expoConfig?.version ?? '0.1.0',
};

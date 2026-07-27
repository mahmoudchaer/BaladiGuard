const DEFAULT_API_BASE_URL = 'http://localhost:8000';
const DEFAULT_STAFF_USERNAME = 'staff';
const DEFAULT_STAFF_PASSWORD = 'staff-demo-password';

export const config = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL,
  useMockData: import.meta.env.VITE_USE_MOCK_DATA === 'true',
  staffAuth: {
    username: import.meta.env.VITE_STAFF_USERNAME ?? DEFAULT_STAFF_USERNAME,
    password: import.meta.env.VITE_STAFF_PASSWORD ?? DEFAULT_STAFF_PASSWORD,
  },
};

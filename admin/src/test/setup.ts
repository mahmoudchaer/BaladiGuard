import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';

import { resetLocaleForTests } from '@/i18n';
import { LOCALE_STORAGE_KEY } from '@/i18n/storage';

afterEach(() => {
  vi.unstubAllGlobals();
  resetLocaleForTests();
  document.documentElement.lang = 'en';
  document.documentElement.dir = 'ltr';
  window.localStorage.removeItem(LOCALE_STORAGE_KEY);
});

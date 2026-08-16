import { parseAppLocale, type AppLocale } from '@/i18n';

export const LOCALE_STORAGE_KEY = 'baladiguard.locale';

export function loadStoredLocale(): AppLocale {
  try {
    return parseAppLocale(window.localStorage.getItem(LOCALE_STORAGE_KEY));
  } catch {
    return 'en';
  }
}

export function persistLocale(locale: AppLocale): void {
  try {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  } catch {
    // Preference stays in memory when storage is unavailable.
  }
}

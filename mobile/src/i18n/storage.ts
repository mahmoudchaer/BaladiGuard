import * as SecureStore from 'expo-secure-store';

import { parseAppLocale, type AppLocale } from '@/i18n';

export const LOCALE_STORAGE_KEY = 'baladiguard.locale';

export async function loadStoredLocale(): Promise<AppLocale> {
  try {
    const raw = await SecureStore.getItemAsync(LOCALE_STORAGE_KEY);
    return parseAppLocale(raw);
  } catch {
    return 'en';
  }
}

export async function persistLocale(locale: AppLocale): Promise<void> {
  await SecureStore.setItemAsync(LOCALE_STORAGE_KEY, locale);
}

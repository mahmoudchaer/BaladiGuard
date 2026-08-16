import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { I18nManager, View } from 'react-native';

import { getLocale, isRtlLocale, setLocale, subscribeLocale, t, type AppLocale } from '@/i18n';
import { loadStoredLocale, persistLocale } from '@/i18n/storage';

type LocaleContextValue = {
  locale: AppLocale;
  isRtl: boolean;
  t: typeof t;
  setLocalePreference: (locale: AppLocale) => Promise<void>;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<AppLocale>(getLocale);

  useEffect(() => subscribeLocale(() => setLocaleState(getLocale())), []);

  useEffect(() => {
    void loadStoredLocale().then((stored) => {
      setLocale(stored);
    });
  }, []);

  useEffect(() => {
    if (typeof process !== 'undefined' && process.env.VITEST) {
      return;
    }
    const rtl = isRtlLocale(locale);
    if (I18nManager.isRTL !== rtl) {
      I18nManager.allowRTL(rtl);
      I18nManager.forceRTL(rtl);
    }
  }, [locale]);

  const value = useMemo<LocaleContextValue>(
    () => ({
      locale,
      isRtl: isRtlLocale(locale),
      t,
      setLocalePreference: async (next) => {
        setLocale(next);
        await persistLocale(next);
      },
    }),
    [locale],
  );

  return (
    <LocaleContext.Provider value={value}>
      <View style={{ flex: 1, direction: value.isRtl ? 'rtl' : 'ltr' }}>{children}</View>
    </LocaleContext.Provider>
  );
}

export function useI18n(): LocaleContextValue {
  const context = useContext(LocaleContext);
  if (!context) {
    throw new Error('useI18n must be used within LocaleProvider');
  }
  return context;
}

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { getLocale, isRtlLocale, setLocale, subscribeLocale, t, type AppLocale } from '@/i18n';
import { loadStoredLocale, persistLocale } from '@/i18n/storage';

type LocaleContextValue = {
  locale: AppLocale;
  isRtl: boolean;
  t: typeof t;
  setLocalePreference: (locale: AppLocale) => void;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<AppLocale>(getLocale);

  useEffect(() => subscribeLocale(() => setLocaleState(getLocale())), []);

  useEffect(() => {
    setLocale(loadStoredLocale());
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = isRtlLocale(locale) ? 'rtl' : 'ltr';
  }, [locale]);

  const value = useMemo<LocaleContextValue>(
    () => ({
      locale,
      isRtl: isRtlLocale(locale),
      t,
      setLocalePreference: (next) => {
        setLocale(next);
        persistLocale(next);
      },
    }),
    [locale],
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

// Context and hook stay together so the provider contract stays atomic.
// eslint-disable-next-line react-refresh/only-export-components
export function useI18n(): LocaleContextValue {
  const context = useContext(LocaleContext);
  if (!context) {
    throw new Error('useI18n must be used within LocaleProvider');
  }
  return context;
}

import ar from './locales/ar.json';
import en from './locales/en.json';
import fr from './locales/fr.json';

export const SUPPORTED_LOCALES = ['en', 'ar', 'fr'] as const;
export type AppLocale = (typeof SUPPORTED_LOCALES)[number];

const CATALOGS: Record<AppLocale, Record<string, unknown>> = { en, ar, fr };

type Listener = () => void;

let currentLocale: AppLocale = 'en';
const listeners = new Set<Listener>();

export function isAppLocale(value: string | null | undefined): value is AppLocale {
  return value === 'en' || value === 'ar' || value === 'fr';
}

export function parseAppLocale(value: string | null | undefined): AppLocale {
  return isAppLocale(value) ? value : 'en';
}

export function getLocale(): AppLocale {
  return currentLocale;
}

export function isRtlLocale(locale: AppLocale = currentLocale): boolean {
  return locale === 'ar';
}

function lookup(tree: unknown, path: string): string | undefined {
  let node: unknown = tree;
  for (const part of path.split('.')) {
    if (!node || typeof node !== 'object' || !(part in node)) {
      return undefined;
    }
    node = (node as Record<string, unknown>)[part];
  }
  return typeof node === 'string' ? node : undefined;
}

function interpolate(template: string, vars?: Record<string, string | number>): string {
  if (!vars) {
    return template;
  }
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in vars ? String(vars[name]) : match,
  );
}

export function t(key: string, vars?: Record<string, string | number>): string {
  const localized = lookup(CATALOGS[currentLocale], key);
  const fallback = localized ?? lookup(CATALOGS.en, key);
  if (fallback == null) {
    if (import.meta.env.DEV) {
      console.warn(`[i18n] missing key: ${key}`);
    }
    return key;
  }
  return interpolate(fallback, vars);
}

export function setLocale(next: AppLocale): void {
  if (currentLocale === next) {
    return;
  }
  currentLocale = next;
  listeners.forEach((listener) => listener());
}

export function subscribeLocale(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function resetLocaleForTests(): void {
  currentLocale = 'en';
  listeners.clear();
}

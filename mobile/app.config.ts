/**
 * Expo dynamic config for BaladiGuard citizen app.
 *
 * Static base fields live in `app.json`. This module extends that base with
 * notification deep-link (#257) Universal Links / Android App Links for the
 * host matching backend `CITIZEN_APP_BASE_URL`.
 *
 * Set EXPO_PUBLIC_CITIZEN_APP_HOST (hostname only) or
 * EXPO_PUBLIC_CITIZEN_APP_BASE_URL (full https URL) so the claimed host matches
 * the backend. See docs/notifications.md.
 */
import type { ConfigContext, ExpoConfig } from 'expo/config';

// CJS helper: Expo evaluates config via require-from-string (no TS path resolution).
// eslint-disable-next-line @typescript-eslint/no-require-imports
const { resolveCitizenAppLinkHost } = require('./citizenAppLinkHost.js') as {
  resolveCitizenAppLinkHost: (
    env?: NodeJS.ProcessEnv | Record<string, string | undefined>,
  ) => string;
};

export default ({ config }: ConfigContext): ExpoConfig => {
  const citizenAppLinkHost = resolveCitizenAppLinkHost();

  return {
    ...config,
    name: config.name ?? 'BaladiGuard',
    slug: config.slug ?? 'baladiguard',
    scheme: config.scheme ?? 'baladiguard',
    ios: {
      ...config.ios,
      bundleIdentifier: config.ios?.bundleIdentifier ?? 'com.baladiguard.citizen',
      associatedDomains: [
        ...new Set([...(config.ios?.associatedDomains ?? []), `applinks:${citizenAppLinkHost}`]),
      ],
    },
    android: {
      ...config.android,
      package: config.android?.package ?? 'com.baladiguard.citizen',
      intentFilters: [
        ...(config.android?.intentFilters ?? []),
        {
          action: 'VIEW',
          autoVerify: true,
          data: [
            {
              scheme: 'https',
              host: citizenAppLinkHost,
              pathPrefix: '/t',
            },
          ],
          category: ['BROWSABLE', 'DEFAULT'],
        },
      ],
    },
    extra: {
      ...config.extra,
      citizenAppLinkHost,
    },
  };
};

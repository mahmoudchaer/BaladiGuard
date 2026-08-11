/**
 * Expo config for BaladiGuard citizen app.
 *
 * Notification deep links (#257) emit HTTPS URLs
 * `{CITIZEN_APP_BASE_URL}/t/{code}`. For installed builds to open those URLs
 * in-app (not only in a browser), the native app must claim the host via:
 * - iOS Associated Domains (`applinks:<host>`)
 * - Android App Links intent filters (`https` + host + `/t` path prefix)
 *
 * Set EXPO_PUBLIC_CITIZEN_APP_HOST (hostname only) or
 * EXPO_PUBLIC_CITIZEN_APP_BASE_URL (full https URL) so the claimed host matches
 * the backend CITIZEN_APP_BASE_URL. See docs/notifications.md.
 */

const appJson = require('./app.json');
const { resolveCitizenAppLinkHost } = require('./citizenAppLinkHost');

const citizenAppLinkHost = resolveCitizenAppLinkHost();

/** @type {import('expo/config').ExpoConfig} */
const expo = {
  ...appJson.expo,
  scheme: 'baladiguard',
  ios: {
    ...(appJson.expo.ios || {}),
    bundleIdentifier:
      (appJson.expo.ios && appJson.expo.ios.bundleIdentifier) || 'com.baladiguard.citizen',
    associatedDomains: [
      ...new Set([
        ...((appJson.expo.ios && appJson.expo.ios.associatedDomains) || []),
        `applinks:${citizenAppLinkHost}`,
      ]),
    ],
  },
  android: {
    ...(appJson.expo.android || {}),
    package: (appJson.expo.android && appJson.expo.android.package) || 'com.baladiguard.citizen',
    intentFilters: [
      ...((appJson.expo.android && appJson.expo.android.intentFilters) || []),
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
    ...(appJson.expo.extra || {}),
    citizenAppLinkHost,
  },
};

module.exports = { expo };

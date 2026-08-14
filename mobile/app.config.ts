/**
 * Expo dynamic config for BaladiGuard citizen app (issues #192 / #257).
 *
 * Static base fields live in `app.json`. This module adds signed-release
 * identifiers, still-image-only photo permissions, and notification deep-link
 * Universal Links / Android App Links for the host matching backend
 * `CITIZEN_APP_BASE_URL`.
 *
 * Production/release builds must inject:
 * - EXPO_PUBLIC_APP_ENV=production
 * - EXPO_PUBLIC_ENABLE_MOCK_API=false
 * - EXPO_PUBLIC_API_BASE_URL=https://<approved-api-host>/v1
 *
 * Set EXPO_PUBLIC_CITIZEN_APP_HOST (hostname only) or
 * EXPO_PUBLIC_CITIZEN_APP_BASE_URL (full https URL) so the claimed host matches
 * the backend. See docs/mobile-release.md and docs/notifications.md.
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
  const plugins = (config.plugins ?? []).map((plugin) => {
    if (Array.isArray(plugin) && plugin[0] === 'expo-image-picker') {
      const options = typeof plugin[1] === 'object' && plugin[1] ? plugin[1] : {};
      return [
        'expo-image-picker',
        {
          ...options,
          microphonePermission: false,
        },
      ];
    }
    return plugin;
  });

  return {
    ...config,
    name: config.name ?? 'BaladiGuard',
    slug: config.slug ?? 'baladiguard',
    version: config.version ?? '0.1.0',
    scheme: config.scheme ?? 'baladiguard',
    icon: config.icon ?? './assets/icon.png',
    splash: config.splash ?? {
      image: './assets/splash-icon.png',
      resizeMode: 'contain',
      backgroundColor: '#F4F6F8',
    },
    plugins,
    ios: {
      ...config.ios,
      bundleIdentifier: config.ios?.bundleIdentifier ?? 'com.baladiguard.citizen',
      buildNumber: config.ios?.buildNumber ?? '1',
      supportsTablet: false,
      associatedDomains: [
        ...new Set([...(config.ios?.associatedDomains ?? []), `applinks:${citizenAppLinkHost}`]),
      ],
      infoPlist: {
        ...config.ios?.infoPlist,
        NSCameraUsageDescription:
          config.ios?.infoPlist?.NSCameraUsageDescription ??
          'Allow BaladiGuard to access your camera so you can take a photo of the issue.',
        NSPhotoLibraryUsageDescription:
          config.ios?.infoPlist?.NSPhotoLibraryUsageDescription ??
          'Allow BaladiGuard to access your photos so you can attach issue images.',
        NSPhotoLibraryAddUsageDescription:
          config.ios?.infoPlist?.NSPhotoLibraryAddUsageDescription ??
          'Allow BaladiGuard to save issue photos you capture for your report.',
        NSLocationWhenInUseUsageDescription:
          config.ios?.infoPlist?.NSLocationWhenInUseUsageDescription ??
          'Allow BaladiGuard to use your location to pin the issue where you are.',
      },
      privacyManifests: {
        NSPrivacyAccessedAPITypes: [
          {
            NSPrivacyAccessedAPIType: 'NSPrivacyAccessedAPICategoryUserDefaults',
            NSPrivacyAccessedAPITypeReasons: ['CA92.1'],
          },
        ],
      },
    },
    android: {
      ...config.android,
      package: config.android?.package ?? 'com.baladiguard.citizen',
      versionCode: config.android?.versionCode ?? 1,
      adaptiveIcon: config.android?.adaptiveIcon ?? {
        foregroundImage: './assets/adaptive-icon.png',
        backgroundColor: '#007A3D',
      },
      permissions: [
        'android.permission.CAMERA',
        'android.permission.ACCESS_COARSE_LOCATION',
        'android.permission.ACCESS_FINE_LOCATION',
        'android.permission.READ_MEDIA_IMAGES',
      ],
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
      eas: {
        projectId: process.env.EAS_PROJECT_ID || undefined,
      },
      privacyPolicyUrl:
        process.env.EXPO_PUBLIC_PRIVACY_POLICY_URL ||
        'https://github.com/mahmoudchaer/BaladiGuard/blob/main/docs/privacy-lifecycle.md',
      appEnv: process.env.EXPO_PUBLIC_APP_ENV || 'local',
    },
  };
};

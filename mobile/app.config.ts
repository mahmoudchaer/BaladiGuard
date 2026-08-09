import type { ConfigContext, ExpoConfig } from 'expo/config';

/**
 * Expo app config for the BaladiGuard citizen app (issue #192).
 *
 * Production/release builds must inject:
 * - EXPO_PUBLIC_APP_ENV=production
 * - EXPO_PUBLIC_ENABLE_MOCK_API=false
 * - EXPO_PUBLIC_API_BASE_URL=https://<approved-api-host>/v1
 *
 * See docs/mobile-release.md.
 */
export default ({ config }: ConfigContext): ExpoConfig => ({
  ...config,
  name: 'BaladiGuard',
  slug: 'baladiguard',
  version: '0.1.0',
  orientation: 'portrait',
  scheme: 'baladiguard',
  userInterfaceStyle: 'light',
  newArchEnabled: true,
  icon: './assets/icon.png',
  splash: {
    image: './assets/splash-icon.png',
    resizeMode: 'contain',
    backgroundColor: '#F4F6F8',
  },
  android: {
    package: 'com.baladiguard.citizen',
    versionCode: 1,
    adaptiveIcon: {
      foregroundImage: './assets/adaptive-icon.png',
      backgroundColor: '#007A3D',
    },
    permissions: [
      'android.permission.CAMERA',
      'android.permission.ACCESS_COARSE_LOCATION',
      'android.permission.ACCESS_FINE_LOCATION',
      'android.permission.READ_MEDIA_IMAGES',
    ],
  },
  ios: {
    bundleIdentifier: 'com.baladiguard.citizen',
    buildNumber: '1',
    supportsTablet: false,
    infoPlist: {
      NSCameraUsageDescription:
        'Allow BaladiGuard to access your camera so you can take a photo of the issue.',
      NSPhotoLibraryUsageDescription:
        'Allow BaladiGuard to access your photos so you can attach issue images.',
      NSPhotoLibraryAddUsageDescription:
        'Allow BaladiGuard to save issue photos you capture for your report.',
      NSLocationWhenInUseUsageDescription:
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
  plugins: [
    'expo-router',
    [
      'expo-image-picker',
      {
        photosPermission: 'Allow BaladiGuard to access your photos so you can attach issue images.',
        cameraPermission:
          'Allow BaladiGuard to access your camera so you can take a photo of the issue.',
        // Still-image only — do not request microphone for production manifests.
        microphonePermission: false,
      },
    ],
    [
      'expo-location',
      {
        locationWhenInUsePermission:
          'Allow BaladiGuard to use your location to pin the issue where you are.',
      },
    ],
    'expo-asset',
    'expo-font',
    'expo-secure-store',
  ],
  experiments: {
    typedRoutes: true,
    tsconfigPaths: true,
  },
  extra: {
    // Filled by `eas init` / EAS project linking. Do not invent credentials here.
    eas: {
      projectId: process.env.EAS_PROJECT_ID || undefined,
    },
    // Override in production with the municipality-hosted policy URL.
    privacyPolicyUrl:
      process.env.EXPO_PUBLIC_PRIVACY_POLICY_URL ||
      'https://github.com/mahmoudchaer/BaladiGuard/blob/main/docs/privacy-lifecycle.md',
    appEnv: process.env.EXPO_PUBLIC_APP_ENV || 'local',
  },
});

#!/usr/bin/env node
/**
 * Release readiness checks for issue #192.
 *
 * Validates assets, EAS profiles, resolved Expo config (not just source tokens),
 * Expo SDK compatibility, and a production-like export bundle so Metro env
 * inlining failures cannot slip through.
 */

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const errors = [];
const REVIEW_API_URL = 'https://api.review.example/v1';
const expoCli = path.join(root, 'node_modules', 'expo', 'bin', 'cli');
const expoDoctorJs = path.join(root, 'node_modules', 'expo-doctor', 'build', 'index.js');

function requireFile(relativePath) {
  const absolute = path.join(root, relativePath);
  if (!fs.existsSync(absolute)) {
    errors.push(`Missing required file: ${relativePath}`);
    return null;
  }
  return absolute;
}

function requireNonEmptyPng(relativePath) {
  const absolute = requireFile(relativePath);
  if (!absolute) {
    return;
  }
  const size = fs.statSync(absolute).size;
  if (size < 500) {
    errors.push(`Asset looks empty or invalid: ${relativePath} (${size} bytes)`);
  }
}

function runNodeScript(scriptPath, args, options = {}) {
  return spawnSync(process.execPath, [scriptPath, ...args], {
    cwd: root,
    encoding: 'utf8',
    env: options.env || process.env,
  });
}

for (const asset of [
  'assets/icon.png',
  'assets/adaptive-icon.png',
  'assets/splash.png',
  'assets/splash-icon.png',
]) {
  requireNonEmptyPng(asset);
}

const easPath = requireFile('eas.json');
if (easPath) {
  const eas = JSON.parse(fs.readFileSync(easPath, 'utf8'));
  const production = eas?.build?.production;
  if (!production) {
    errors.push('eas.json must define a production build profile.');
  } else {
    const env = production.env || {};
    if (env.EXPO_PUBLIC_APP_ENV !== 'production') {
      errors.push('eas.json production profile must set EXPO_PUBLIC_APP_ENV=production.');
    }
    if (env.EXPO_PUBLIC_ENABLE_MOCK_API !== 'false') {
      errors.push('eas.json production profile must set EXPO_PUBLIC_ENABLE_MOCK_API=false.');
    }
  }
  if (!eas?.build?.preview) {
    errors.push('eas.json must define a preview (internal) build profile.');
  }
}

const gitignorePath = requireFile('.gitignore');
if (gitignorePath) {
  const gitignore = fs.readFileSync(gitignorePath, 'utf8');
  for (const pattern of ['*.jks', '*.keystore', 'credentials.json', 'google-services.json']) {
    if (!gitignore.includes(pattern)) {
      errors.push(`mobile/.gitignore must ignore ${pattern}`);
    }
  }
}

if (!fs.existsSync(path.join(root, '..', 'docs', 'mobile-release.md'))) {
  errors.push('Missing docs/mobile-release.md release runbook.');
}

requireFile('app.config.ts');

const configSourceRuntime = requireFile('src/services/config.ts');
if (configSourceRuntime) {
  const source = fs.readFileSync(configSourceRuntime, 'utf8');
  for (const token of [
    'process.env.EXPO_PUBLIC_API_BASE_URL',
    'process.env.EXPO_PUBLIC_ENABLE_MOCK_API',
    'process.env.EXPO_PUBLIC_APP_ENV',
  ]) {
    if (!source.includes(token)) {
      errors.push(`config.ts must reference ${token} literally for Metro inlining.`);
    }
  }
  if (source.includes('http://localhost:8000') || source.includes('DEFAULT_LOCAL_API')) {
    errors.push(
      'config.ts must not embed a localhost API default constant (set EXPO_PUBLIC_API_BASE_URL via mobile/.env).',
    );
  }
}

// Introspected Expo config applies config plugins and exposes the generated
// native manifest, catching permission drift beyond source tokens.
try {
  if (!fs.existsSync(expoCli)) {
    throw new Error('expo CLI missing — run npm ci in mobile/');
  }
  const resolvedResult = runNodeScript(expoCli, ['config', '--json', '--type', 'introspect']);
  if (resolvedResult.status !== 0) {
    throw new Error(
      (resolvedResult.stderr || resolvedResult.stdout || 'expo config failed').trim(),
    );
  }
  const resolvedRaw = resolvedResult.stdout || '';
  const jsonStart = resolvedRaw.indexOf('{');
  if (jsonStart < 0) {
    throw new Error('expo config --json produced no JSON object');
  }
  const resolved = JSON.parse(resolvedRaw.slice(jsonStart));
  if (resolved.android?.package !== 'com.baladiguard.citizen') {
    errors.push('Resolved Expo config android.package must be com.baladiguard.citizen.');
  }
  if (resolved.ios?.bundleIdentifier !== 'com.baladiguard.citizen') {
    errors.push('Resolved Expo config ios.bundleIdentifier must be com.baladiguard.citizen.');
  }
  if (!resolved.icon) {
    errors.push('Resolved Expo config is missing icon.');
  }
  const splashPlugin = (resolved.plugins || []).find(
    (entry) =>
      entry === 'expo-splash-screen' || (Array.isArray(entry) && entry[0] === 'expo-splash-screen'),
  );
  if (!splashPlugin) {
    errors.push('Resolved Expo config missing expo-splash-screen plugin.');
  }
  const infoPlist = resolved.ios?.infoPlist || {};
  for (const key of [
    'NSCameraUsageDescription',
    'NSPhotoLibraryUsageDescription',
    'NSLocationWhenInUseUsageDescription',
  ]) {
    if (!infoPlist[key]) {
      errors.push(`Resolved Expo config missing ios.infoPlist.${key}`);
    }
  }
  const plugins = resolved.plugins || [];
  const imagePicker = plugins.find(
    (entry) => Array.isArray(entry) && entry[0] === 'expo-image-picker',
  );
  if (!imagePicker) {
    errors.push('Resolved Expo config missing expo-image-picker plugin.');
  } else if (imagePicker[1]?.microphonePermission !== false) {
    errors.push(
      'Resolved Expo config must set expo-image-picker.microphonePermission=false (no RECORD_AUDIO).',
    );
  }
  const manifest = resolved._internal?.modResults?.android?.manifest?.manifest;
  const usesPermissions = manifest?.['uses-permission'] || [];
  const activeRecordAudio = usesPermissions.some((permission) => {
    const attributes = permission?.$ || {};
    return (
      attributes['android:name'] === 'android.permission.RECORD_AUDIO' &&
      attributes['tools:node'] !== 'remove'
    );
  });
  if (activeRecordAudio) {
    errors.push('Generated Android manifest must not request android.permission.RECORD_AUDIO.');
  }
} catch (error) {
  errors.push(`Failed to resolve Expo config: ${error.message || error}`);
}

// Native SDK compatibility (expo-doctor / install --check).
if (!fs.existsSync(expoDoctorJs)) {
  errors.push('expo-doctor is not installed — run npm ci in mobile/.');
} else {
  const doctor = runNodeScript(expoDoctorJs, []);
  if (doctor.status !== 0) {
    errors.push(`expo-doctor failed:\n${((doctor.stdout || '') + (doctor.stderr || '')).trim()}`);
  }
}

const installCheck = runNodeScript(expoCli, ['install', '--check']);
if (installCheck.status !== 0) {
  errors.push(
    `expo install --check failed:\n${((installCheck.stdout || '') + (installCheck.stderr || '')).trim()}`,
  );
}

// Production-like export proving Metro inlined the HTTPS API URL.
const exportDir = fs.mkdtempSync(path.join(os.tmpdir(), 'baladiguard-release-export-'));
const exportEnv = {
  ...process.env,
  EXPO_PUBLIC_APP_ENV: 'production',
  EXPO_PUBLIC_ENABLE_MOCK_API: 'false',
  EXPO_PUBLIC_API_BASE_URL: REVIEW_API_URL,
  CI: '1',
};
const exportResult = runNodeScript(
  expoCli,
  ['export', '--platform', 'android', '--output-dir', exportDir],
  { env: exportEnv },
);
if (exportResult.status !== 0) {
  errors.push(
    `Production-like expo export failed:\n${((exportResult.stdout || '') + (exportResult.stderr || '')).trim()}`,
  );
} else {
  let combined = '';
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
        continue;
      }
      // Scan JS/Hermes text outputs from expo export.
      if (
        !/\.(js|hbc|json|txt)$/i.test(entry.name) &&
        !full.includes(`${path.sep}_expo${path.sep}`)
      ) {
        continue;
      }
      try {
        combined += `\n${fs.readFileSync(full, 'utf8')}`;
      } catch {
        // binary / unreadable
      }
    }
  };
  walk(exportDir);
  if (!combined.includes(REVIEW_API_URL)) {
    errors.push(
      `Production export bundle does not embed ${REVIEW_API_URL}. Metro likely failed to inline EXPO_PUBLIC_API_BASE_URL.`,
    );
  }
  if (combined.includes('http://localhost:8000') || combined.includes('localhost:8000/v1')) {
    errors.push('Production export bundle still contains localhost API fallback.');
  }
  if (/ENABLE_MOCK_API["']?\s*[:=]\s*["']?true/.test(combined)) {
    errors.push('Production export bundle appears to enable mock API.');
  }
}

try {
  fs.rmSync(exportDir, { recursive: true, force: true });
} catch {
  // best-effort cleanup
}

if (errors.length > 0) {
  console.error('Release readiness checks failed:\n');
  for (const error of errors) {
    console.error(`- ${error}`);
  }
  process.exit(1);
}

console.log('Release readiness checks passed (resolved config, expo-doctor, production export).');

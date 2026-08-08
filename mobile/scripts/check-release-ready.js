#!/usr/bin/env node
/**
 * Static release readiness checks for issue #192.
 * Does not talk to EAS or require signing credentials.
 */

const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const errors = [];

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

for (const asset of [
  'assets/icon.png',
  'assets/adaptive-icon.png',
  'assets/splash.png',
  'assets/splash-icon.png',
]) {
  requireNonEmptyPng(asset);
}

const appConfigPath = requireFile('app.config.ts');
if (appConfigPath) {
  const source = fs.readFileSync(appConfigPath, 'utf8');
  for (const token of [
    "package: 'com.baladiguard.citizen'",
    "bundleIdentifier: 'com.baladiguard.citizen'",
    'icon: ',
    'NSCameraUsageDescription',
    'NSPhotoLibraryUsageDescription',
    'NSLocationWhenInUseUsageDescription',
  ]) {
    if (!source.includes(token)) {
      errors.push(`app.config.ts is missing expected release metadata: ${token}`);
    }
  }
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

if (errors.length > 0) {
  console.error('Release readiness checks failed:\n');
  for (const error of errors) {
    console.error(`- ${error}`);
  }
  process.exit(1);
}

console.log('Release readiness checks passed.');

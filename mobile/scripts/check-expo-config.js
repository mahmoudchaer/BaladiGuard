#!/usr/bin/env node
/**
 * Fail CI if Expo cannot load the project config, or if notification deep links
 * (#257) are missing native host registration.
 */
const fs = require('node:fs');
const path = require('node:path');

const { getConfig } = require('@expo/config');

const root = process.cwd();

const DYNAMIC_CONFIGS = ['app.config.ts', 'app.config.js', 'app.config.mjs', 'app.config.cjs'];
const hasDynamic = DYNAMIC_CONFIGS.some((name) => fs.existsSync(path.join(root, name)));
const hasStatic = fs.existsSync(path.join(root, 'app.json'));

if (!hasDynamic && !hasStatic) {
  console.error('No Expo config found (expected app.config.ts and/or app.json).');
  process.exit(1);
}

if (hasDynamic && !hasStatic) {
  console.warn(
    'Warning: no app.json static base. Dynamic config must define all required Expo fields.',
  );
}

let exp;
try {
  ({ exp } = getConfig(root, {
    skipSDKVersionRequirement: true,
    // Plugins need a full install + native modules; CI only needs the resolved config shape.
    skipPlugins: true,
  }));
} catch (error) {
  console.error('Failed to load Expo config:');
  console.error(error);
  process.exit(1);
}

const errors = [];

if (!exp?.scheme) {
  errors.push('expo.scheme is required (citizen app uses baladiguard).');
}

const associated = exp?.ios?.associatedDomains ?? [];
if (!associated.some((entry) => typeof entry === 'string' && entry.startsWith('applinks:'))) {
  errors.push(
    'ios.associatedDomains must include applinks:<host> for HTTPS notification deep links (#257).',
  );
}

const filters = exp?.android?.intentFilters ?? [];
const hasHttpsTicketFilter = filters.some((filter) => {
  if (filter?.action !== 'VIEW' || !filter?.autoVerify) {
    return false;
  }
  const dataEntries = Array.isArray(filter.data) ? filter.data : filter.data ? [filter.data] : [];
  return dataEntries.some(
    (data) =>
      data?.scheme === 'https' &&
      typeof data?.host === 'string' &&
      data.host.length > 0 &&
      data?.pathPrefix === '/t',
  );
});
if (!hasHttpsTicketFilter) {
  errors.push('android.intentFilters must auto-verify https://<host>/t for App Links (#257).');
}

const host = exp?.extra?.citizenAppLinkHost;
if (typeof host !== 'string' || !host.trim()) {
  errors.push('extra.citizenAppLinkHost must be set so runtime can read the claimed host.');
}

if (errors.length > 0) {
  console.error('Expo config check failed:');
  for (const message of errors) {
    console.error(`- ${message}`);
  }
  process.exit(1);
}

console.log(
  JSON.stringify(
    {
      status: 'ok',
      dynamicConfig: hasDynamic,
      staticConfig: hasStatic,
      scheme: exp.scheme,
      citizenAppLinkHost: host,
      associatedDomains: associated,
      androidIntentFilterCount: filters.length,
    },
    null,
    2,
  ),
);

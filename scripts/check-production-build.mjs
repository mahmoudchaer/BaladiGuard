#!/usr/bin/env node
/**
 * Verify that the admin production bundle was built with the required
 * environment variables and does not contain local-development fallbacks.
 *
 * Usage: node scripts/check-production-build.mjs [dist-dir]
 *
 * This script is called by `npm run check:production-build --prefix admin`
 * after `npm run build --prefix admin` in the deploy workflow.
 */

import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const distDir = process.argv[2] || resolve(__dirname, '..', 'admin', 'dist');

// ---------------------------------------------------------------------------
// 1. Find the built JS bundle(s)
// ---------------------------------------------------------------------------

if (!existsSync(distDir)) {
  console.error(`::error::dist directory not found: ${distDir}`);
  process.exit(1);
}

const assetsDir = `${distDir}/assets`;
if (!existsSync(assetsDir)) {
  console.error(`::error::assets directory not found: ${assetsDir}`);
  process.exit(1);
}

const jsFiles = readdirSync(assetsDir).filter((f) => f.endsWith('.js'));
if (jsFiles.length === 0) {
  console.error('::error::No JS bundle found in dist/assets');
  process.exit(1);
}

// Concatenate all JS files for searching
let bundle = '';
for (const file of jsFiles) {
  bundle += readFileSync(`${assetsDir}/${file}`, 'utf-8');
}

// ---------------------------------------------------------------------------
// 2. Checks
// ---------------------------------------------------------------------------
let failed = false;

function fail(msg) {
  console.error(`::error::${msg}`);
  failed = true;
}

// Match both quote styles and template literals the minifier may emit.
function containsAny(patterns) {
  return patterns.some((p) => bundle.includes(p));
}

// 2a. VITE_APP_ENV must not be "local" (the #312 default).
if (containsAny(['appEnv:"local"', "appEnv:'local'", 'appEnv:`local`'])) {
  fail('VITE_APP_ENV is "local" — production builds must set VITE_APP_ENV=staging|production');
}

// 2b. API base URL must not fall back to localhost.
if (bundle.includes('http://localhost:8000')) {
  fail('Bundle contains http://localhost:8000 — VITE_API_BASE_URL was not set or fell back to localhost');
}

// 2c. Mock data must be disabled.
if (containsAny(['useMockData:!0', 'useMockData:true'])) {
  fail('VITE_USE_MOCK_DATA is true — production builds must set VITE_USE_MOCK_DATA=false');
}

// 2d. No staff credentials leaked.
if (bundle.includes('staff-demo-password')) {
  fail('Bundle contains staff-demo-password — VITE_STAFF_PASSWORD must not be set in production');
}

// 2e. VITE_APP_ENV must appear as a non-local value.
if (!containsAny(['appEnv:"staging"', 'appEnv:"production"', "appEnv:'staging'", "appEnv:'production'", 'appEnv:`staging`', 'appEnv:`production`'])) {
  fail('Bundle does not contain APP_ENV=staging|production — VITE_APP_ENV may not be set');
}

if (failed) {
  process.exit(1);
}

console.log('Production build checks passed.');

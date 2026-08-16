#!/usr/bin/env node
/**
 * Fail CI when locale catalogs drift or contain empty strings.
 * Usage: node scripts/check-i18n.mjs <locales-dir>
 */
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

const localesDir = resolve(process.argv[2] || '');
if (!localesDir) {
  console.error('Usage: node scripts/check-i18n.mjs <locales-dir>');
  process.exit(1);
}

function flatten(value, prefix = '', out = {}) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    for (const [key, child] of Object.entries(value)) {
      flatten(child, prefix ? `${prefix}.${key}` : key, out);
    }
    return out;
  }
  out[prefix] = value;
  return out;
}

const files = readdirSync(localesDir).filter((name) => name.endsWith('.json')).sort();
if (files.length < 2) {
  console.error(`Expected at least two locale JSON files in ${localesDir}`);
  process.exit(1);
}

const catalogs = files.map((name) => {
  const raw = JSON.parse(readFileSync(join(localesDir, name), 'utf8'));
  return { locale: name.replace(/\.json$/, ''), keys: flatten(raw) };
});

const baseline = catalogs[0];
let failed = false;

for (const catalog of catalogs) {
  const missing = Object.keys(baseline.keys).filter((key) => !(key in catalog.keys));
  const extra = Object.keys(catalog.keys).filter((key) => !(key in baseline.keys));
  const empty = Object.entries(catalog.keys)
    .filter(([, value]) => typeof value !== 'string' || value.trim() === '')
    .map(([key]) => key);
  if (missing.length || extra.length || empty.length) {
    failed = true;
    console.error(`Locale ${catalog.locale}:`);
    if (missing.length) console.error(`  missing: ${missing.join(', ')}`);
    if (extra.length) console.error(`  extra: ${extra.join(', ')}`);
    if (empty.length) console.error(`  empty: ${empty.join(', ')}`);
  }
}

if (failed) {
  process.exit(1);
}

console.log(
  `i18n catalogs OK (${catalogs.map((item) => item.locale).join(', ')}; ${Object.keys(baseline.keys).length} keys)`,
);

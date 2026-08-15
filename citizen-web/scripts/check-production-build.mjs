import fs from 'node:fs';
import path from 'node:path';

const dist = path.resolve(process.cwd(), 'dist');

if (!fs.existsSync(dist)) {
  console.error('dist/ is missing. Run a production Vite build first.');
  process.exit(1);
}

function walk(dir) {
  const files = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...walk(full));
    } else {
      files.push(full);
    }
  }
  return files;
}

const files = walk(dist);
const maps = files.filter((file) => file.endsWith('.map'));
if (maps.length > 0) {
  console.error('Production source maps must not be published:');
  for (const file of maps) {
    console.error(`  ${path.relative(dist, file)}`);
  }
  process.exit(1);
}

const text = files
  .filter((file) => /\.(js|css|html|json|txt)$/i.test(file))
  .map((file) => fs.readFileSync(file, 'utf8'))
  .join('\n');

const forbidden = [
  [/AKIA[0-9A-Z]{16}/, 'AWS access key id'],
  [/aws[_-]?secret[_-]?access[_-]?key/i, 'AWS secret key name'],
  [/BEGIN (?:RSA |OPENSSH )?PRIVATE KEY/, 'private key material'],
  [/VITE_USE_MOCK_DATA["']?\s*[:=]\s*["']?true/i, 'mock-data flag'],
  [/\buseMockData\s*:\s*true\b/, 'compiled mock mode'],
  [/\bdemo@baladiguard\b/i, 'demo credential'],
  [/password\s*[:=]\s*["'](?:admin|demo|password)["']/i, 'demo password'],
];

if (process.env.VITE_APP_ENV === 'production' || process.env.VITE_APP_ENV === 'staging') {
  // Fail-closed config still mentions localhost so it can reject it. The compiled
  // production env must not actually select that default as the API origin.
  forbidden.push([
    /VITE_API_BASE_URL:\s*[`'"]https?:\/\/(?:localhost|127\.0\.0\.1)/,
    'localhost compiled as VITE_API_BASE_URL',
  ]);
}

let failed = false;
for (const [pattern, label] of forbidden) {
  if (pattern.test(text)) {
    console.error(`Production bundle contains ${label}.`);
    failed = true;
  }
}

const apiBase = (process.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '');
if (apiBase && !text.includes(apiBase)) {
  console.error(`Production bundle does not embed VITE_API_BASE_URL=${apiBase}.`);
  failed = true;
}

if (failed) {
  process.exit(1);
}

console.log('Production citizen-web bundle checks passed.');

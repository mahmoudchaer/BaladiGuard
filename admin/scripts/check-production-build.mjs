import fs from 'node:fs';
import path from 'node:path';

const dist = path.resolve(process.cwd(), 'dist');
const appEnv = (process.env.VITE_APP_ENV ?? '').trim();
const apiBase = (process.env.VITE_API_BASE_URL ?? '').trim().replace(/\/+$/, '');
const errors = [];

if (!['staging', 'production'].includes(appEnv))
  errors.push('VITE_APP_ENV must be staging or production.');
if (process.env.VITE_USE_MOCK_DATA !== 'false')
  errors.push('VITE_USE_MOCK_DATA must be explicitly false.');
if (process.env.VITE_STAFF_USERNAME || process.env.VITE_STAFF_PASSWORD)
  errors.push('Demo staff credentials must not be supplied to a deployed build.');
try {
  const url = new URL(apiBase);
  if (
    url.protocol !== 'https:' ||
    ['localhost', '127.0.0.1', '::1', '[::1]'].includes(url.hostname) ||
    url.username ||
    url.password
  ) {
    errors.push('VITE_API_BASE_URL must be a non-localhost HTTPS origin.');
  }
} catch {
  errors.push('VITE_API_BASE_URL must be a valid absolute URL.');
}
if (!fs.existsSync(dist)) errors.push('dist/ is missing; build the admin application first.');

if (errors.length === 0) {
  const files = fs.readdirSync(dist, { recursive: true }).map(String);
  if (files.some((file) => file.endsWith('.map')))
    errors.push('Production source maps must not be published.');
  const text = files
    .filter((file) => /\.(?:js|css|html|json|txt)$/i.test(file))
    .map((file) => fs.readFileSync(path.join(dist, file), 'utf8'))
    .join('\n');
  if (!text.includes(apiBase))
    errors.push('The configured API origin was not embedded in the build.');
  if (text.includes('staff-demo-password'))
    errors.push('The build contains the demo staff password.');
  if (/AKIA[0-9A-Z]{16}|BEGIN (?:RSA |OPENSSH )?PRIVATE KEY/.test(text))
    errors.push('The build contains credential-like material.');
}

if (errors.length) {
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}
console.log('Production admin bundle checks passed.');

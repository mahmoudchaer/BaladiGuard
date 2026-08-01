import { readFileSync } from 'node:fs';

const [, , reportPath, exceptionsPath, scope] = process.argv;
const report = JSON.parse(readFileSync(reportPath, 'utf8'));
const exceptions = JSON.parse(readFileSync(exceptionsPath, 'utf8'))[scope] ?? [];
const allowed = new Set(exceptions.flatMap((item) => item.advisories));
const today = new Date().toISOString().slice(0, 10);
const failures = [];

for (const [name, vulnerability] of Object.entries(report.vulnerabilities ?? {})) {
  if (!['high', 'critical'].includes(vulnerability.severity)) continue;
  const advisories = (vulnerability.via ?? [])
    .filter((item) => typeof item === 'object')
    .map((item) => item.url?.split('/').pop())
    .filter(Boolean);
  const expired = exceptions.some(
    (item) => item.advisories.some((advisory) => advisories.includes(advisory)) && item.expires < today,
  );
  const unexpected = advisories.filter((advisory) => !allowed.has(advisory));
  if (vulnerability.severity === 'critical' || expired || unexpected.length > 0) {
    failures.push({ name, severity: vulnerability.severity, advisories, unexpected, expired });
  } else {
    console.log(`EXCEPTION ${name}: ${advisories.join(', ')}`);
  }
}

if (failures.length > 0) {
  console.error(JSON.stringify({ failures }, null, 2));
  process.exit(1);
}

import { readFileSync } from 'node:fs';

const [, , reportPath, exceptionsPath, scope] = process.argv;
const report = JSON.parse(readFileSync(reportPath, 'utf8'));
const exceptions = JSON.parse(readFileSync(exceptionsPath, 'utf8'))[scope] ?? [];
const allowed = new Set(exceptions.flatMap((item) => item.advisories));
const today = new Date().toISOString().slice(0, 10);
const failures = [];
const dayMilliseconds = 24 * 60 * 60 * 1000;
const issuePattern = /^https:\/\/github\.com\/[^/]+\/[^/]+\/issues\/\d+$/;
const datePattern = /^\d{4}-\d{2}-\d{2}$/;
const configurationFailures = [];

for (const [index, exception] of exceptions.entries()) {
  const label = `${scope}[${index}]`;
  if (!Array.isArray(exception.advisories) || exception.advisories.length === 0) {
    configurationFailures.push(`${label}.advisories must be a non-empty array`);
  }
  if (!issuePattern.test(exception.issue ?? '')) {
    configurationFailures.push(`${label}.issue must link to a GitHub issue`);
  }
  if (!datePattern.test(exception.created ?? '') || !datePattern.test(exception.expires ?? '')) {
    configurationFailures.push(`${label}.created and .expires must use YYYY-MM-DD`);
  } else {
    const duration = (Date.parse(exception.expires) - Date.parse(exception.created)) / dayMilliseconds;
    if (duration < 0 || duration > 30) {
      configurationFailures.push(`${label} must expire within 30 days of creation`);
    }
    if (exception.expires < today) configurationFailures.push(`${label} is expired`);
  }
}

if (configurationFailures.length > 0) {
  console.error(JSON.stringify({ configurationFailures }, null, 2));
  process.exit(1);
}

function collectAdvisories(packageName, seen = new Set()) {
  if (seen.has(packageName)) return [];
  seen.add(packageName);
  const vulnerability = report.vulnerabilities?.[packageName];
  if (!vulnerability) return [];
  return (vulnerability.via ?? []).flatMap((item) => {
    if (typeof item === 'string') return collectAdvisories(item, seen);
    const advisory = item.url?.split('/').pop();
    return advisory ? [advisory] : [];
  });
}

for (const [name, vulnerability] of Object.entries(report.vulnerabilities ?? {})) {
  if (!['high', 'critical'].includes(vulnerability.severity)) continue;
  const advisories = [...new Set(collectAdvisories(name))];
  const unexpected = advisories.filter((advisory) => !allowed.has(advisory));
  const unidentified = advisories.length === 0;
  if (vulnerability.severity === 'critical' || unidentified || unexpected.length > 0) {
    failures.push({ name, severity: vulnerability.severity, advisories, unexpected, unidentified });
  } else {
    console.log(`EXCEPTION ${name}: ${advisories.join(', ')}`);
  }
}

if (failures.length > 0) {
  console.error(JSON.stringify({ failures }, null, 2));
  process.exit(1);
}

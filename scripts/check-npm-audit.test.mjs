import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';

const script = new URL('./check-npm-audit.mjs', import.meta.url);

function runGate(report, exceptions) {
  const directory = mkdtempSync(join(tmpdir(), 'npm-audit-gate-'));
  const reportPath = join(directory, 'report.json');
  const exceptionsPath = join(directory, 'exceptions.json');
  writeFileSync(reportPath, JSON.stringify(report));
  writeFileSync(exceptionsPath, JSON.stringify({ test: exceptions }));
  return spawnSync(process.execPath, [script.pathname, reportPath, exceptionsPath, 'test'], {
    encoding: 'utf8',
  });
}

test('fails closed when a high finding has only string via entries', () => {
  const result = runGate(
    { vulnerabilities: { vulnerable: { severity: 'high', via: ['transitive-package'] } } },
    [],
  );
  assert.equal(result.status, 1);
  assert.match(result.stderr, /"unidentified": true/);
});

test('resolves advisory IDs through referenced transitive packages', () => {
  const result = runGate(
    {
      vulnerabilities: {
        parent: { severity: 'high', via: ['child'] },
        child: {
          severity: 'high',
          via: [{ url: 'https://github.com/advisories/GHSA-test' }],
        },
      },
    },
    [
      {
        advisories: ['GHSA-test'],
        created: '2026-08-01',
        expires: '2026-08-31',
        issue: 'https://github.com/example/project/issues/1',
      },
    ],
  );
  assert.equal(result.status, 0, result.stderr);
});

test('rejects an exception without a linked issue', () => {
  const result = runGate(
    { vulnerabilities: {} },
    [{ advisories: ['GHSA-test'], created: '2026-08-01', expires: '2026-08-31' }],
  );
  assert.equal(result.status, 1);
  assert.match(result.stderr, /issue must link to a GitHub issue/);
});

test('allows an identified high finding with a valid time-boxed exception', () => {
  const result = runGate(
    {
      vulnerabilities: {
        vulnerable: {
          severity: 'high',
          via: [{ url: 'https://github.com/advisories/GHSA-test' }],
        },
      },
    },
    [
      {
        advisories: ['GHSA-test'],
        created: '2026-08-01',
        expires: '2026-08-31',
        issue: 'https://github.com/example/project/issues/1',
      },
    ],
  );
  assert.equal(result.status, 0, result.stderr);
});

#!/usr/bin/env node
/**
 * Fail when critical-flow TSX still contains user-facing English literals.
 * Usage: node scripts/check-hardcoded-ui.mjs <app-src-dir>
 */
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

const root = resolve(process.argv[2] || '');
if (!root) {
  console.error('Usage: node scripts/check-hardcoded-ui.mjs <app-src-dir>');
  process.exit(1);
}

const TARGETS = [
  'pages/HomePage.tsx',
  'pages/LoginPage.tsx',
  'pages/ReportPage.tsx',
  'pages/ProfilePage.tsx',
  'pages/HistoryPage.tsx',
  'pages/TrackPage.tsx',
  'pages/PublicReportsPage.tsx',
  'pages/PublicDetailPage.tsx',
  'pages/MapPage.tsx',
  'pages/PrivacyPage.tsx',
  'pages/NotFoundPage.tsx',
  'pages/TicketListPage.tsx',
  'pages/TicketDetailPage.tsx',
  'pages/MapViewPage.tsx',
  'pages/WorkforcePage.tsx',
  'components/PublicPhoto.tsx',
  'components/ImageRedactionReview.tsx',
  'components/StaffAssistantPanel.tsx',
];

const ATTR = /(aria-label|title|placeholder|alt|label)=["']([A-Za-z][^"']{2,})["']/g;
const TEXT = />([A-Za-z][^<{]{2,})</g;
const ALLOWED = new Set([
  'BaladiGuard',
  'B',
  'SMS',
  'GET',
  'POST',
  'ALL',
  'NONE',
  'EMAIL',
  'BOTH',
  'LB',
  'US',
  'FR',
  'GB',
]);

function isAllowed(value) {
  const trimmed = value.replace(/\s+/g, ' ').trim();
  if (!trimmed || ALLOWED.has(trimmed)) return true;
  if (/^[\d\s./·—–-]+$/.test(trimmed)) return true;
  if (/^status\./.test(trimmed) || /^category\./.test(trimmed)) return true;
  if (!/[A-Za-z]{3,}/.test(trimmed)) return true;
  if (trimmed.includes('{') || trimmed.includes('t(')) return true;
  return false;
}

const findings = [];
for (const relative of TARGETS) {
  const file = join(root, relative);
  let source;
  try {
    source = readFileSync(file, 'utf8');
  } catch {
    continue;
  }
  for (const match of source.matchAll(ATTR)) {
    if (!isAllowed(match[2])) {
      findings.push(`${relative}: ${match[1]}="${match[2]}"`);
    }
  }
  for (const match of source.matchAll(TEXT)) {
    if (!isAllowed(match[1])) {
      findings.push(`${relative}: >${match[1].trim()}<`);
    }
  }
}

if (findings.length) {
  console.error('Hard-coded UI strings remain in critical flows:');
  for (const item of findings) {
    console.error(`  ${item}`);
  }
  process.exit(1);
}

console.log(`Hard-coded UI check OK (${root})`);

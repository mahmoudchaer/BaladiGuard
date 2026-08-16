#!/usr/bin/env node
/**
 * Fail when critical-flow TSX still contains user-facing English literals.
 * Usage: node scripts/check-hardcoded-ui.mjs <app-src-dir>
 */
import { readFileSync } from 'node:fs';
import { basename, dirname, join, resolve } from 'node:path';

const root = resolve(process.argv[2] || '');
if (!root) {
  console.error('Usage: node scripts/check-hardcoded-ui.mjs <app-src-dir>');
  process.exit(1);
}

const TARGETS = {
  mobile: [
    'app/(tabs)/index.tsx',
    'app/(tabs)/explore.tsx',
    'app/(tabs)/history.tsx',
    'app/profile/index.tsx',
    'app/public/[ticketNumber].tsx',
    'app/t/[code].tsx',
    'src/features/citizen-auth/OtpVerifyForm.tsx',
    'src/features/citizen-auth/PhoneEntryForm.tsx',
    'src/features/citizen-report/ReportForm.tsx',
    'src/features/citizen-report/components/DetailsStep.tsx',
    'src/features/citizen-report/components/LocationFields.tsx',
    'src/features/citizen-report/components/PhotoPickerField.tsx',
    'src/features/citizen-report/components/ReviewSummary.tsx',
    'src/features/citizen-report/components/ReportSuccess.tsx',
    'src/features/citizen-report/components/StepProgress.tsx',
    'src/features/profile/ProfileSummary.tsx',
    'src/features/profile/ProfileEditForm.tsx',
    'src/features/profile/ChangePhoneFlow.tsx',
    'src/features/ticket-tracking/TrackLookupForm.tsx',
    'src/features/public-browse/PublicReportFilters.tsx',
    'src/features/public-browse/PublicReportsMap.tsx',
  ],
  admin: [
    'pages/LoginPage.tsx',
    'pages/TicketListPage.tsx',
    'pages/TicketDetailPage.tsx',
    'pages/MapViewPage.tsx',
    'pages/WorkforcePage.tsx',
    'components/ImageRedactionReview.tsx',
    'components/StaffAssistantPanel.tsx',
    'components/TicketPreviewPanel.tsx',
  ],
  'citizen-web': [
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
    'pages/NotificationLinkPage.tsx',
    'components/PublicPhoto.tsx',
  ],
};

function appIdFromRoot(dir) {
  const name = basename(dir);
  return name === 'src' ? basename(dirname(dir)) : name;
}

const appId = appIdFromRoot(root);
const targets = TARGETS[appId];
if (!targets) {
  console.error(`Unknown app root for hard-coded UI check: ${root}`);
  process.exit(1);
}

const ATTR =
  /(aria-label|title|placeholder|alt|label|accessibilityLabel|accessibilityHint)=["']([A-Za-z][^"']{2,})["']/g;
const ALERT = /Alert\.alert\(\s*['"]([A-Za-z][^'"]+)['"]/g;
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
for (const relative of targets) {
  const file = join(root, relative);
  let source;
  try {
    source = readFileSync(file, 'utf8');
  } catch {
    findings.push(`${relative}: missing file`);
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
  for (const match of source.matchAll(ALERT)) {
    if (!isAllowed(match[1])) {
      findings.push(`${relative}: Alert.alert("${match[1]}")`);
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

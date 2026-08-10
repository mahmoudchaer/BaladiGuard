/**
 * Device-local report drafts (issue #258).
 *
 * Stored in SecureStore, keyed by citizen userId. Never log draft contents.
 * Photo bytes are not stored — only local URI / metadata and optional upload key.
 */

import * as SecureStore from 'expo-secure-store';

import type { ReportFormValues } from '@/schemas/reportFormSchema';
import type { ReportWizardStepKey } from '@/features/citizen-report/components/StepProgress';

export const REPORT_DRAFT_VERSION = 1 as const;

export type ReportDraftSubmissionState = {
  clientSubmissionId: string;
  imageObjectKey?: string;
};

export type ReportDraft = {
  version: typeof REPORT_DRAFT_VERSION;
  ownerUserId: string;
  updatedAt: number;
  step: ReportWizardStepKey;
  form: {
    description: string;
    addressText: string;
    latitude?: number;
    longitude?: number;
    locationSource: ReportFormValues['locationSource'];
    photoUri: string;
    photoFileName?: string;
    photoContentType?: string;
  };
  selectedPlaceholderId?: string;
  submission?: ReportDraftSubmissionState;
};

const STORAGE_PREFIX = 'baladiguard.reportDraft.';

export function reportDraftStorageKey(ownerUserId: string): string {
  return `${STORAGE_PREFIX}${ownerUserId.trim()}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object';
}

function isWizardStep(value: unknown): value is ReportWizardStepKey {
  return value === 'details' || value === 'photo' || value === 'location' || value === 'review';
}

export function isReportDraft(value: unknown): value is ReportDraft {
  if (!isRecord(value)) {
    return false;
  }
  if (value.version !== REPORT_DRAFT_VERSION) {
    return false;
  }
  if (typeof value.ownerUserId !== 'string' || !value.ownerUserId.trim()) {
    return false;
  }
  if (typeof value.updatedAt !== 'number' || !Number.isFinite(value.updatedAt)) {
    return false;
  }
  if (!isWizardStep(value.step)) {
    return false;
  }
  if (!isRecord(value.form)) {
    return false;
  }
  const form = value.form;
  if (typeof form.description !== 'string' || typeof form.addressText !== 'string') {
    return false;
  }
  if (typeof form.photoUri !== 'string') {
    return false;
  }
  if (
    form.locationSource !== 'GPS' &&
    form.locationSource !== 'MANUAL' &&
    form.locationSource !== 'PLACEHOLDER'
  ) {
    return false;
  }
  if (value.submission !== undefined) {
    if (!isRecord(value.submission)) {
      return false;
    }
    if (typeof value.submission.clientSubmissionId !== 'string') {
      return false;
    }
  }
  return true;
}

/** Build a storage-safe id for Idempotency-Key (8–128 [A-Za-z0-9_-]). */
export function createClientSubmissionId(): string {
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789';
  const bytes = new Uint8Array(24);
  if (typeof globalThis.crypto?.getRandomValues === 'function') {
    globalThis.crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) {
      bytes[i] = Math.floor(Math.random() * 256);
    }
  }
  let out = 'sub-';
  for (let i = 0; i < bytes.length; i += 1) {
    out += alphabet[bytes[i]! % alphabet.length];
  }
  return out;
}

export function draftToFormValues(draft: ReportDraft): ReportFormValues {
  return {
    description: draft.form.description,
    addressText: draft.form.addressText,
    latitude: draft.form.latitude,
    longitude: draft.form.longitude,
    locationSource: draft.form.locationSource,
    photoUri: draft.form.photoUri,
    photoFileName: draft.form.photoFileName ?? '',
    photoContentType: draft.form.photoContentType ?? '',
  };
}

export function buildReportDraft(input: {
  ownerUserId: string;
  step: ReportWizardStepKey;
  form: ReportFormValues;
  selectedPlaceholderId?: string;
  submission?: ReportDraftSubmissionState;
  previous?: ReportDraft | null;
}): ReportDraft {
  return {
    version: REPORT_DRAFT_VERSION,
    ownerUserId: input.ownerUserId.trim(),
    updatedAt: Date.now(),
    step: input.step,
    form: {
      description: input.form.description,
      addressText: input.form.addressText,
      latitude: input.form.latitude,
      longitude: input.form.longitude,
      locationSource: input.form.locationSource,
      photoUri: input.form.photoUri,
      photoFileName: input.form.photoFileName,
      photoContentType: input.form.photoContentType,
    },
    selectedPlaceholderId: input.selectedPlaceholderId,
    submission: input.submission ?? input.previous?.submission,
  };
}

/** True when the draft has enough content worth offering restore. */
export function draftHasRestorableContent(draft: ReportDraft): boolean {
  if (draft.form.description.trim().length > 0) {
    return true;
  }
  if (draft.form.addressText.trim().length > 0) {
    return true;
  }
  if (draft.form.photoUri.trim().length > 0) {
    return true;
  }
  if (draft.form.latitude !== undefined && draft.form.longitude !== undefined) {
    return true;
  }
  if (draft.submission?.imageObjectKey) {
    return true;
  }
  return false;
}

export async function loadReportDraft(ownerUserId: string): Promise<ReportDraft | null> {
  const key = reportDraftStorageKey(ownerUserId);
  let raw: string | null;
  try {
    raw = await SecureStore.getItemAsync(key);
  } catch {
    return null;
  }
  if (!raw) {
    return null;
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!isReportDraft(parsed)) {
      await clearReportDraft(ownerUserId);
      return null;
    }
    if (parsed.ownerUserId !== ownerUserId.trim()) {
      await clearReportDraft(ownerUserId);
      return null;
    }
    return parsed;
  } catch {
    await clearReportDraft(ownerUserId);
    return null;
  }
}

export async function saveReportDraft(draft: ReportDraft): Promise<void> {
  if (!draft.ownerUserId.trim()) {
    throw new Error('Cannot save draft without an owner.');
  }
  const key = reportDraftStorageKey(draft.ownerUserId);
  // Never include secrets beyond form fields already known to the citizen.
  await SecureStore.setItemAsync(key, JSON.stringify(draft));
}

export async function clearReportDraft(ownerUserId: string): Promise<void> {
  const key = reportDraftStorageKey(ownerUserId);
  try {
    await SecureStore.deleteItemAsync(key);
  } catch {
    // Best-effort clear.
  }
}

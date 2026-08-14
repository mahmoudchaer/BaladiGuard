import { beforeEach, describe, expect, it } from 'vitest';

import {
  buildReportDraft,
  clearReportDraft,
  createClientSubmissionId,
  draftHasRestorableContent,
  draftToFormValues,
  isReportDraft,
  loadReportDraft,
  reportDraftStorageKey,
  saveReportDraft,
  type ReportDraft,
} from '@/services/reportDraft';
import { __getSecureStoreMock, __resetSecureStoreMock } from '@/test/mocks/expo-secure-store';

const baseForm = {
  description: 'Large pothole near the gate causing slow traffic.',
  addressText: 'Hamra, Beirut',
  latitude: 33.89,
  longitude: 35.48,
  locationSource: 'GPS' as const,
  photoUri: 'file:///photo.jpg',
  photoFileName: 'photo.jpg',
  photoContentType: 'image/jpeg',
};

describe('reportDraft', () => {
  beforeEach(() => {
    __resetSecureStoreMock();
  });

  it('persists and restores a draft for the same owner only', async () => {
    const draft = buildReportDraft({
      ownerUserId: 'usr_a',
      step: 'location',
      form: baseForm,
      submission: {
        clientSubmissionId: 'sub-testkey1234567890abcd',
        imageObjectKey: 'reports/photos/key.jpg',
      },
    });
    await saveReportDraft(draft);

    const loaded = await loadReportDraft('usr_a');
    expect(loaded).not.toBeNull();
    expect(loaded?.step).toBe('location');
    expect(loaded?.submission?.imageObjectKey).toBe('reports/photos/key.jpg');
    expect(draftToFormValues(loaded!).description).toContain('pothole');
    expect(await loadReportDraft('usr_b')).toBeNull();
  });

  it('rejects cross-user payloads and clears corrupt storage', async () => {
    __getSecureStoreMock().set(
      reportDraftStorageKey('usr_a'),
      JSON.stringify({
        version: 1,
        ownerUserId: 'usr_other',
        updatedAt: Date.now(),
        step: 'details',
        form: {
          description: 'x',
          addressText: '',
          locationSource: 'MANUAL',
          photoUri: '',
        },
      }),
    );
    expect(await loadReportDraft('usr_a')).toBeNull();
    expect(__getSecureStoreMock().has(reportDraftStorageKey('usr_a'))).toBe(false);
  });

  it('clears on explicit discard', async () => {
    await saveReportDraft(
      buildReportDraft({ ownerUserId: 'usr_a', step: 'details', form: baseForm }),
    );
    await clearReportDraft('usr_a');
    expect(await loadReportDraft('usr_a')).toBeNull();
  });

  it('detects restorable content and creates valid submission ids', () => {
    const empty = buildReportDraft({
      ownerUserId: 'usr_a',
      step: 'details',
      form: {
        description: '',
        addressText: '',
        locationSource: 'MANUAL',
        photoUri: '',
        photoFileName: '',
        photoContentType: '',
      },
    });
    expect(draftHasRestorableContent(empty)).toBe(false);
    expect(
      draftHasRestorableContent(
        buildReportDraft({ ownerUserId: 'u', step: 'photo', form: baseForm }),
      ),
    ).toBe(true);

    const id = createClientSubmissionId();
    expect(id.length).toBeGreaterThanOrEqual(8);
    expect(/^[A-Za-z0-9_-]+$/.test(id)).toBe(true);
  });

  it('isReportDraft validates shape', () => {
    const good: ReportDraft = buildReportDraft({
      ownerUserId: 'usr_a',
      step: 'review',
      form: baseForm,
    });
    expect(isReportDraft(good)).toBe(true);
    expect(isReportDraft({ ...good, version: 99 })).toBe(false);
    expect(isReportDraft({ ...good, step: 'nope' })).toBe(false);
  });
});

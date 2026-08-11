import { afterEach, describe, expect, it } from 'vitest';

import {
  checkLocalPhotoUri,
  isLocalDevicePhotoUri,
  PHOTO_REFERENCE_EXPIRED_MESSAGE,
} from '@/services/photoReference';
import {
  buildReportDraft,
  clearUnusableDraftPhoto,
  draftToFormValues,
} from '@/services/reportDraft';
import {
  __resetFileSystemMock,
  __setFileInfoResolver,
  getInfoAsync,
} from '@/test/mocks/expo-file-system';

describe('photoReference', () => {
  afterEach(() => {
    __resetFileSystemMock();
  });

  it('classifies local device schemes', () => {
    expect(isLocalDevicePhotoUri('file:///tmp/a.jpg')).toBe(true);
    expect(isLocalDevicePhotoUri('content://media/1')).toBe(true);
    expect(isLocalDevicePhotoUri('https://cdn.example/a.jpg')).toBe(false);
  });

  it('treats remote URIs as reachable without probing disk', async () => {
    let probed = false;
    __setFileInfoResolver(async () => {
      probed = true;
      return { exists: true };
    });
    const result = await checkLocalPhotoUri('https://example.com/a.jpg');
    expect(result.ok).toBe(true);
    expect(probed).toBe(false);
  });

  it('returns empty for blank URIs', async () => {
    expect(await checkLocalPhotoUri('')).toEqual({ ok: false, reason: 'empty' });
  });

  it('accepts an existing device photo URI via FileSystem existence check', async () => {
    const uri = 'file:///data/user/0/com.baladiguard.citizen/cache/photo.jpg';
    const seen: string[] = [];
    __setFileInfoResolver(async (fileUri) => {
      seen.push(fileUri);
      return { exists: true, uri: fileUri, size: 1024, isDirectory: false, modificationTime: 1 };
    });

    const result = await checkLocalPhotoUri(uri);
    expect(result).toEqual({ ok: true });
    expect(seen).toEqual([uri]);
    // Mock getInfoAsync remains callable for cross-file imports.
    await expect(getInfoAsync(uri)).resolves.toMatchObject({ exists: true });
  });

  it('rejects a missing device photo URI deterministically', async () => {
    __setFileInfoResolver(async () => ({ exists: false }));

    const result = await checkLocalPhotoUri('file:///tmp/expired-picker-photo.jpg');
    expect(result).toEqual({ ok: false, reason: 'missing' });
  });

  it('marks FileSystem failures as unreachable instead of accepting the URI', async () => {
    __setFileInfoResolver(async () => {
      throw new Error('native module unavailable');
    });

    const result = await checkLocalPhotoUri('content://media/external/images/media/1');
    expect(result).toEqual({ ok: false, reason: 'unreachable' });
  });

  it('clearUnusableDraftPhoto keeps description and uploaded key', () => {
    const draft = buildReportDraft({
      ownerUserId: 'usr_a',
      step: 'review',
      form: {
        description: 'Pothole near campus',
        addressText: 'Hamra',
        latitude: 33.8,
        longitude: 35.5,
        locationSource: 'GPS',
        photoUri: 'file:///gone.jpg',
        photoFileName: 'gone.jpg',
        photoContentType: 'image/jpeg',
      },
      submission: {
        clientSubmissionId: 'sub-aaaaaaaaaaaaaaaaaaaaaa',
        imageObjectKey: 'reports/photos/keep.jpg',
      },
    });
    const cleaned = clearUnusableDraftPhoto(draft);
    expect(cleaned.form.photoUri).toBe('');
    expect(cleaned.form.description).toContain('Pothole');
    expect(cleaned.submission?.imageObjectKey).toBe('reports/photos/keep.jpg');
    expect(draftToFormValues(cleaned).photoUri).toBe('');
    expect(PHOTO_REFERENCE_EXPIRED_MESSAGE).toMatch(/photo/i);
  });
});

import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('expo-file-system', () => ({
  getInfoAsync: vi.fn(async () => ({ exists: false })),
}));

import * as FileSystem from 'expo-file-system';
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

describe('photoReference', () => {
  afterEach(() => {
    vi.mocked(FileSystem.getInfoAsync).mockReset();
    vi.mocked(FileSystem.getInfoAsync).mockResolvedValue({ exists: false } as Awaited<
      ReturnType<typeof FileSystem.getInfoAsync>
    >);
  });

  it('classifies local device schemes', () => {
    expect(isLocalDevicePhotoUri('file:///tmp/a.jpg')).toBe(true);
    expect(isLocalDevicePhotoUri('content://media/1')).toBe(true);
    expect(isLocalDevicePhotoUri('https://cdn.example/a.jpg')).toBe(false);
  });

  it('treats remote URIs as reachable without probing disk', async () => {
    const result = await checkLocalPhotoUri('https://example.com/a.jpg');
    expect(result.ok).toBe(true);
    expect(FileSystem.getInfoAsync).not.toHaveBeenCalled();
  });

  it('returns empty for blank URIs', async () => {
    expect(await checkLocalPhotoUri('')).toEqual({ ok: false, reason: 'empty' });
  });

  it('accepts an existing device photo URI via FileSystem existence check', async () => {
    vi.mocked(FileSystem.getInfoAsync).mockResolvedValueOnce({
      exists: true,
      uri: 'file:///data/user/0/com.baladiguard.citizen/cache/photo.jpg',
      size: 1024,
      isDirectory: false,
      modificationTime: 1,
    } as Awaited<ReturnType<typeof FileSystem.getInfoAsync>>);

    const uri = 'file:///data/user/0/com.baladiguard.citizen/cache/photo.jpg';
    const result = await checkLocalPhotoUri(uri);
    expect(result).toEqual({ ok: true });
    expect(FileSystem.getInfoAsync).toHaveBeenCalledWith(uri);
  });

  it('rejects a missing device photo URI deterministically', async () => {
    vi.mocked(FileSystem.getInfoAsync).mockResolvedValueOnce({
      exists: false,
      uri: 'file:///tmp/expired-picker-photo.jpg',
      isDirectory: false,
    } as Awaited<ReturnType<typeof FileSystem.getInfoAsync>>);

    const result = await checkLocalPhotoUri('file:///tmp/expired-picker-photo.jpg');
    expect(result).toEqual({ ok: false, reason: 'missing' });
    expect(FileSystem.getInfoAsync).toHaveBeenCalledWith('file:///tmp/expired-picker-photo.jpg');
  });

  it('marks FileSystem failures as unreachable instead of accepting the URI', async () => {
    vi.mocked(FileSystem.getInfoAsync).mockRejectedValueOnce(
      new Error('native module unavailable'),
    );

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

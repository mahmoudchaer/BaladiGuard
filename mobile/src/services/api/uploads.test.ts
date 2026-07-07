import { beforeEach, describe, expect, it, vi } from 'vitest';

import { uploadReportPhoto } from '@/services/api/uploads';

vi.mock('@/services/config', () => ({
  appConfig: {
    apiBaseUrl: 'http://localhost:8000/v1',
    appVersion: '0.1.0',
  },
}));

const photo = {
  uri: 'file:///photo.jpg',
  fileName: 'photo.jpg',
  contentType: 'image/jpeg',
};

describe('uploadReportPhoto', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('returns imageObjectKey from a successful upload response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ imageObjectKey: 'reports/photos/test.jpg' }),
      }),
    );

    await expect(uploadReportPhoto(photo)).resolves.toBe('reports/photos/test.jpg');
  });

  it('throws when the upload request fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({ error: { message: 'Image file must be 5MB or smaller.' } }),
      }),
    );

    await expect(uploadReportPhoto(photo)).rejects.toThrow('Image file must be 5MB or smaller.');
  });

  it('throws when a successful response is missing imageObjectKey', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({}),
      }),
    );

    await expect(uploadReportPhoto(photo)).rejects.toThrow(
      'Photo upload succeeded but no image reference was returned.',
    );
  });
});

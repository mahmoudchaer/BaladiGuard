import { describe, expect, it } from 'vitest';

import { reportFormSchema, reportFormSchemaWithUploadedPhoto } from '@/schemas/reportFormSchema';

const validReport = {
  description: 'Large pothole blocking the road.',
  addressText: 'AUB Main Gate, Beirut',
  latitude: 33.8961,
  longitude: 35.4784,
  locationSource: 'PLACEHOLDER' as const,
  photoUri: '',
  photoFileName: '',
  photoContentType: '',
};

describe('report form schema', () => {
  it('requires a local photo for a new report', () => {
    const result = reportFormSchema.safeParse(validReport);

    expect(result.success).toBe(false);
    expect(result.error?.issues).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          path: ['photoUri'],
          message: 'Please attach a photo of the issue.',
        }),
      ]),
    );
  });

  it('allows an empty local photo URI when retrying with an uploaded photo', () => {
    expect(reportFormSchemaWithUploadedPhoto.safeParse(validReport).success).toBe(true);
  });
});

import { z } from 'zod';

const reportFormBaseSchema = z.object({
  description: z
    .string()
    .trim()
    .min(10, 'Please describe the issue in at least 10 characters.')
    .max(2000, 'Description must be 2000 characters or fewer.'),
  addressText: z.string().trim().min(3, 'Enter a location or choose a sample place.'),
  latitude: z.number().min(-90).max(90).optional(),
  longitude: z.number().min(-180).max(180).optional(),
  locationSource: z.enum(['GPS', 'MANUAL', 'PLACEHOLDER']),
  photoUri: z.string(),
  photoFileName: z.string().optional(),
  photoContentType: z.string().optional(),
});

function validateLocation(data: z.infer<typeof reportFormBaseSchema>, ctx: z.RefinementCtx): void {
  if (data.latitude === undefined || data.longitude === undefined) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Look up an address, tap the map, or choose a sample location.',
      path: ['addressText'],
    });
  }
}

export const reportFormSchema = reportFormBaseSchema.superRefine((data, ctx) => {
  if (!data.photoUri.trim()) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Please attach a photo of the issue.',
      path: ['photoUri'],
    });
  }
  validateLocation(data, ctx);
});

/** Retries may use a photo uploaded before its device-local URI expired. */
export const reportFormSchemaWithUploadedPhoto = reportFormBaseSchema.superRefine((data, ctx) => {
  validateLocation(data, ctx);
});

export type ReportFormValues = z.infer<typeof reportFormSchema>;

export const defaultReportFormValues: ReportFormValues = {
  description: '',
  addressText: '',
  locationSource: 'MANUAL',
  photoUri: '',
  photoFileName: '',
  photoContentType: '',
};

import { z } from 'zod';

export const reportFormSchema = z
  .object({
    description: z
      .string()
      .trim()
      .min(10, 'Please describe the issue in at least 10 characters.')
      .max(2000, 'Description must be 2000 characters or fewer.'),
    addressText: z.string().trim().min(3, 'Enter a location or choose a sample place.'),
    latitude: z.number().min(-90).max(90).optional(),
    longitude: z.number().min(-180).max(180).optional(),
    locationSource: z.enum(['GPS', 'MANUAL', 'PLACEHOLDER']).default('MANUAL'),
    photoUri: z.string().min(1, 'Please attach a photo of the issue.'),
    photoFileName: z.string().optional(),
    photoContentType: z.string().optional(),
  })
  .superRefine((data, ctx) => {
    if (data.latitude === undefined || data.longitude === undefined) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Look up an address, tap the map, or choose a sample location.',
        path: ['addressText'],
      });
    }
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

import { z } from 'zod';

const phonePattern = /^\+?[0-9\s()-]{7,20}$/;

export const reportFormSchema = z
  .object({
    description: z
      .string()
      .trim()
      .min(10, 'Please describe the issue in at least 10 characters.')
      .max(2000, 'Description must be 2000 characters or fewer.'),
    contactName: z.string().trim().max(120, 'Name is too long.').optional(),
    phone: z
      .string()
      .trim()
      .optional()
      .refine((value) => !value || phonePattern.test(value), {
        message: 'Enter a valid phone number.',
      }),
    email: z
      .string()
      .trim()
      .optional()
      .refine((value) => !value || z.string().email().safeParse(value).success, {
        message: 'Enter a valid email address.',
      }),
    addressText: z
      .string()
      .trim()
      .min(3, 'Enter a location or choose a sample place.'),
    latitude: z.number().optional(),
    longitude: z.number().optional(),
    locationSource: z.enum(['GPS', 'MANUAL', 'PLACEHOLDER']).default('MANUAL'),
    photoUri: z.string().min(1, 'Please attach a photo of the issue.'),
    photoFileName: z.string().optional(),
    photoContentType: z.string().optional(),
  })
  .superRefine((data, ctx) => {
    const hasPhone = Boolean(data.phone?.trim());
    const hasEmail = Boolean(data.email?.trim());

    if (!hasPhone && !hasEmail) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Provide a phone number or email so we can reach you.',
        path: ['phone'],
      });
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Provide a phone number or email so we can reach you.',
        path: ['email'],
      });
    }
  });

export type ReportFormValues = z.infer<typeof reportFormSchema>;

export const defaultReportFormValues: ReportFormValues = {
  description: '',
  contactName: '',
  phone: '',
  email: '',
  addressText: '',
  locationSource: 'MANUAL',
  photoUri: '',
  photoFileName: '',
  photoContentType: '',
};

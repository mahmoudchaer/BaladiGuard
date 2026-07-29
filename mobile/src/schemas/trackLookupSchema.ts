import { z } from 'zod';

import { isValidTrackingCode, normalizeTrackingCode } from '@/utils/trackingCode';

export const TRACKING_CODE_REQUIRED_MESSAGE = 'Enter your tracking code to look up a report.';
export const TRACKING_CODE_INVALID_MESSAGE =
  'Tracking codes are 6 characters using letters A–Z and digits 2–9 (no I, O, 0, or 1).';

export const trackLookupSchema = z.object({
  trackingCode: z
    .string()
    .transform((value) => normalizeTrackingCode(value))
    .superRefine((value, ctx) => {
      if (!value) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: TRACKING_CODE_REQUIRED_MESSAGE,
        });
        return;
      }
      if (!isValidTrackingCode(value)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: TRACKING_CODE_INVALID_MESSAGE,
        });
      }
    }),
});

export type TrackLookupFormValues = z.infer<typeof trackLookupSchema>;

export const defaultTrackLookupValues: TrackLookupFormValues = {
  trackingCode: '',
};

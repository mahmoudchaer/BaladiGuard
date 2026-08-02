import { z } from 'zod';

import { validatePhoneInput } from '@/utils/phone';

export const OTP_CODE_REQUIRED_MESSAGE = 'Enter the 6-digit verification code.';
export const OTP_CODE_INVALID_MESSAGE = 'code must be a 6-digit verification code.';
export const FULL_NAME_REQUIRED_MESSAGE = 'Enter your full name.';
export const FULL_NAME_LENGTH_MESSAGE = 'fullName must be 1–120 characters after trimming.';

export const DEFAULT_PHONE_REGION = 'LB';

export const phoneOtpRequestSchema = z
  .object({
    phone: z.string(),
    region: z.string().optional(),
  })
  .superRefine((data, ctx) => {
    const result = validatePhoneInput(data.phone, data.region);
    if (!result.ok) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: result.message,
        path: ['phone'],
      });
    }
  });

export type PhoneOtpRequestValues = z.infer<typeof phoneOtpRequestSchema>;

export const defaultPhoneOtpRequestValues: PhoneOtpRequestValues = {
  phone: '',
  region: DEFAULT_PHONE_REGION,
};

export const otpVerifySchema = z.object({
  code: z
    .string()
    .trim()
    .superRefine((value, ctx) => {
      if (!value) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: OTP_CODE_REQUIRED_MESSAGE,
        });
        return;
      }
      if (!/^\d{6}$/.test(value)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: OTP_CODE_INVALID_MESSAGE,
        });
      }
    }),
});

export type OtpVerifyValues = z.infer<typeof otpVerifySchema>;

export const defaultOtpVerifyValues: OtpVerifyValues = {
  code: '',
};

export const fullNameSchema = z.object({
  fullName: z
    .string()
    .trim()
    .superRefine((value, ctx) => {
      if (!value) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: FULL_NAME_REQUIRED_MESSAGE,
        });
        return;
      }
      if (value.length > 120) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: FULL_NAME_LENGTH_MESSAGE,
        });
      }
    }),
});

export type FullNameValues = z.infer<typeof fullNameSchema>;

export const defaultFullNameValues: FullNameValues = {
  fullName: '',
};

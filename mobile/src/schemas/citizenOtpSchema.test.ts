import { describe, expect, it } from 'vitest';

import {
  OTP_CODE_INVALID_MESSAGE,
  OTP_CODE_REQUIRED_MESSAGE,
  otpVerifySchema,
  phoneOtpRequestSchema,
} from '@/schemas/citizenOtpSchema';
import { REGION_REQUIRED_MESSAGE } from '@/utils/phone';

describe('citizen OTP schemas', () => {
  it('validates phone and region for OTP request', () => {
    expect(phoneOtpRequestSchema.safeParse({ phone: '+96170123456', region: 'LB' }).success).toBe(
      true,
    );
    const national = phoneOtpRequestSchema.safeParse({ phone: '70123456' });
    expect(national.success).toBe(false);
    if (!national.success) {
      expect(national.error.issues[0]?.message).toBe(REGION_REQUIRED_MESSAGE);
    }
  });

  it('requires a 6-digit OTP code', () => {
    expect(otpVerifySchema.safeParse({ code: '123456' }).success).toBe(true);
    expect(otpVerifySchema.safeParse({ code: '' }).error?.issues[0]?.message).toBe(
      OTP_CODE_REQUIRED_MESSAGE,
    );
    expect(otpVerifySchema.safeParse({ code: '12ab56' }).error?.issues[0]?.message).toBe(
      OTP_CODE_INVALID_MESSAGE,
    );
  });
});

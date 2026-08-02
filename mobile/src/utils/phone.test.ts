import { describe, expect, it } from 'vitest';

import {
  PHONE_E164_MESSAGE,
  PHONE_INVALID_MESSAGE,
  PHONE_PARSE_MESSAGE,
  PHONE_REQUIRED_MESSAGE,
  REGION_INVALID_MESSAGE,
  REGION_REQUIRED_MESSAGE,
  validatePhoneInput,
} from '@/utils/phone';

describe('validatePhoneInput', () => {
  it('accepts compact E.164 numbers without a region', () => {
    expect(validatePhoneInput('+96170123456')).toEqual({
      ok: true,
      phone: '+96170123456',
      region: undefined,
    });
  });

  it('strips formatting from E.164 input', () => {
    expect(validatePhoneInput('+961 70 123 456')).toEqual({
      ok: true,
      phone: '+96170123456',
      region: undefined,
    });
  });

  it('requires a region for national-format numbers', () => {
    expect(validatePhoneInput('70123456')).toEqual({
      ok: false,
      message: REGION_REQUIRED_MESSAGE,
    });
  });

  it('accepts national numbers with an ISO region', () => {
    expect(validatePhoneInput('70 123 456', 'lb')).toEqual({
      ok: true,
      phone: '70123456',
      region: 'LB',
    });
  });

  it('rejects empty phone input', () => {
    expect(validatePhoneInput('   ')).toEqual({
      ok: false,
      message: PHONE_REQUIRED_MESSAGE,
    });
  });

  it('rejects invalid region codes', () => {
    expect(validatePhoneInput('70123456', 'LBN')).toEqual({
      ok: false,
      message: REGION_INVALID_MESSAGE,
    });
  });

  it('rejects non-digit E.164 payloads', () => {
    expect(validatePhoneInput('+96170ABCD')).toEqual({
      ok: false,
      message: PHONE_PARSE_MESSAGE,
    });
  });

  it('rejects E.164 numbers that are too short', () => {
    expect(validatePhoneInput('+96170')).toEqual({
      ok: false,
      message: PHONE_E164_MESSAGE,
    });
  });

  it('rejects national numbers that are too short', () => {
    expect(validatePhoneInput('123', 'LB')).toEqual({
      ok: false,
      message: PHONE_INVALID_MESSAGE,
    });
  });
});

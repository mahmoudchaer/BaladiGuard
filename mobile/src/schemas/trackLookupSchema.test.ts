import { describe, expect, it } from 'vitest';

import {
  TRACKING_CODE_INVALID_MESSAGE,
  TRACKING_CODE_REQUIRED_MESSAGE,
  trackLookupSchema,
} from '@/schemas/trackLookupSchema';

describe('trackLookupSchema', () => {
  it('accepts a valid code and normalizes it', () => {
    const parsed = trackLookupSchema.parse({ trackingCode: '  ab23cd  ' });
    expect(parsed.trackingCode).toBe('AB23CD');
  });

  it('rejects empty input before any API call would happen', () => {
    const result = trackLookupSchema.safeParse({ trackingCode: '' });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe(TRACKING_CODE_REQUIRED_MESSAGE);
    }
  });

  it('rejects whitespace-only input', () => {
    const result = trackLookupSchema.safeParse({ trackingCode: '   ' });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe(TRACKING_CODE_REQUIRED_MESSAGE);
    }
  });

  it('rejects invalid format with a clear message', () => {
    const result = trackLookupSchema.safeParse({ trackingCode: 'AB1OCD' });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe(TRACKING_CODE_INVALID_MESSAGE);
    }
  });
});

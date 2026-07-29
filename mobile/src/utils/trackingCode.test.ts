import { describe, expect, it } from 'vitest';

import {
  TRACKING_CODE_LENGTH,
  isValidTrackingCode,
  normalizeTrackingCode,
} from '@/utils/trackingCode';

describe('normalizeTrackingCode', () => {
  it('trims and uppercases the code', () => {
    expect(normalizeTrackingCode('  ab12cd  ')).toBe('AB12CD');
  });
});

describe('isValidTrackingCode', () => {
  it('accepts a well-formed 6-character code', () => {
    expect(isValidTrackingCode('AB23CD')).toBe(true);
    expect(isValidTrackingCode('ab23cd')).toBe(true);
    expect(isValidTrackingCode('  ab23cd  ')).toBe(true);
  });

  it('rejects empty and whitespace-only input', () => {
    expect(isValidTrackingCode('')).toBe(false);
    expect(isValidTrackingCode('   ')).toBe(false);
  });

  it('rejects wrong lengths', () => {
    expect(isValidTrackingCode('AB23C')).toBe(false);
    expect(isValidTrackingCode('AB23CDE')).toBe(false);
  });

  it('rejects ambiguous alphabet characters', () => {
    expect(isValidTrackingCode('AB1OCD')).toBe(false);
    expect(isValidTrackingCode('ABI0CD')).toBe(false);
    expect(isValidTrackingCode('AB23C!')).toBe(false);
  });

  it('uses the documented length of 6', () => {
    expect(TRACKING_CODE_LENGTH).toBe(6);
  });
});

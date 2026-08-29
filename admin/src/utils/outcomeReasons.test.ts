import { describe, expect, it } from 'vitest';

import { requiredOutcomeKind, reasonsForKind } from '@/utils/outcomeReasons';

describe('requiredOutcomeKind', () => {
  it('requires a resolution reason when resolving work', () => {
    expect(requiredOutcomeKind('IN_PROGRESS', 'RESOLVED')).toBe('resolution');
    expect(reasonsForKind('resolution').some((item) => item.code === 'WORK_COMPLETED')).toBe(true);
  });

  it('requires a rejection reason for early closure', () => {
    expect(requiredOutcomeKind('SUBMITTED', 'CLOSED')).toBe('rejection');
    expect(requiredOutcomeKind('UNDER_REVIEW', 'CLOSED')).toBe('rejection');
  });

  it('requires a closure reason after resolution and preserves that distinction', () => {
    expect(requiredOutcomeKind('RESOLVED', 'CLOSED')).toBe('closure');
    expect(requiredOutcomeKind('UNDER_REVIEW', 'ASSIGNED')).toBeNull();
  });
});

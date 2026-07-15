import { describe, expect, it } from 'vitest';

import { getSelectableTicketStatuses } from '@/utils/statusTransitions';

describe('getSelectableTicketStatuses', () => {
  it('returns only the current status and allowed next statuses', () => {
    expect(getSelectableTicketStatuses('SUBMITTED')).toEqual([
      'SUBMITTED',
      'UNDER_REVIEW',
      'CLOSED',
    ]);
    expect(getSelectableTicketStatuses('ASSIGNED')).toEqual([
      'ASSIGNED',
      'IN_PROGRESS',
      'UNDER_REVIEW',
    ]);
    expect(getSelectableTicketStatuses('CLOSED')).toEqual(['CLOSED']);
  });
});

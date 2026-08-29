import { describe, expect, it } from 'vitest';

import { parseStaffAssistantResponse } from '@/services/staffAssistant';

describe('parseStaffAssistantResponse', () => {
  it('rejects malformed payloads', () => {
    expect(parseStaffAssistantResponse(null)).toBeNull();
    expect(parseStaffAssistantResponse({ message: 'hi' })).toBeNull();
    expect(
      parseStaffAssistantResponse({
        intent: 'invented',
        asOf: '2026-08-15T12:00:00Z',
        message: 'nope',
        count: 1,
      }),
    ).toBeNull();
  });
});

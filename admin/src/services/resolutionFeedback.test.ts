import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/services/config', () => ({
  config: { apiBaseUrl: 'http://localhost:8000', useMockData: false },
}));

vi.mock('@/services/auth', () => ({
  getStaffAuthHeaders: () => ({ Authorization: 'Bearer test-token' }),
}));

describe('resolutionFeedback service', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('loads staff-only feedback including the private note', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          ticketId: 'tkt_123',
          trackingCode: 'ABC123',
          ticketStatus: 'RESOLVED',
          status: 'STILL_UNRESOLVED',
          note: 'Still broken',
          submittedAt: '2026-08-15T10:00:00Z',
          reviewStatus: 'PENDING',
          needsReview: true,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const { fetchResolutionFeedback } = await import('@/services/resolutionFeedback');
    const feedback = await fetchResolutionFeedback('tkt_123');

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/v1/tickets/tkt_123/resolution-feedback',
      { headers: { Authorization: 'Bearer test-token' } },
    );
    expect(feedback.note).toBe('Still broken');
    expect(feedback.needsReview).toBe(true);
  });
});

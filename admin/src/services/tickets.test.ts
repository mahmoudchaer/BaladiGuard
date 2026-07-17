import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Ticket } from '@/types/ticket';

const apiTicket: Ticket = {
  ticketId: 'tkt_123',
  ticketNumber: 'BG-123',
  trackingCode: 'TRACK-123',
  description: 'Broken street light',
  contact: {},
  location: {
    latitude: 33.8938,
    longitude: 35.5018,
    addressText: 'Beirut',
    source: 'GPS',
  },
  imageObjectKey: 'reports/tkt_123.jpg',
  status: 'UNDER_REVIEW',
  category: 'STREET_LIGHTING',
  priority: 'medium',
  createdBy: null,
  municipalityId: null,
  departmentId: null,
  duplicateGroupId: null,
  createdAt: '2026-07-14T10:00:00Z',
  updatedAt: '2026-07-14T10:05:00Z',
};

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe('updateTicketStatus', () => {
  it('uses the real backend status endpoint when mock mode is not explicitly enabled', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
    vi.stubEnv('VITE_USE_MOCK_DATA', undefined);

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(apiTicket), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const { updateTicketStatus } = await import('@/services/tickets');
    const updatedTicket = await updateTicketStatus('tkt_123', 'UNDER_REVIEW');

    expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/v1/tickets/tkt_123/status', {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ status: 'UNDER_REVIEW' }),
    });
    expect(updatedTicket?.status).toBe('UNDER_REVIEW');
  });

  it('preserves ai fields from the ticket read response shape', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
    vi.stubEnv('VITE_USE_MOCK_DATA', undefined);

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          ...apiTicket,
          ai: {
            originalDescription: 'Broken street light',
            cleanedDescription: 'Non-working street light reported on the main road.',
            aiSuggestedCategory: 'street_lighting',
            aiCategoryExplanation: 'Broken street light.',
            aiProcessingStatus: 'completed',
            aiModelVersion: 'amazon.nova-lite-v1:0',
            suggestedCategory: 'street_lighting',
          },
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const { updateTicketStatus } = await import('@/services/tickets');
    const updatedTicket = await updateTicketStatus('tkt_123', 'UNDER_REVIEW');

    expect(updatedTicket?.ai?.originalDescription).toBe('Broken street light');
    expect(updatedTicket?.ai?.cleanedDescription).toContain('street light');
    expect(updatedTicket?.ai?.aiSuggestedCategory).toBe('street_lighting');
    expect(updatedTicket?.ai?.aiProcessingStatus).toBe('completed');
    expect(updatedTicket?.ai?.aiModelVersion).toBe('amazon.nova-lite-v1:0');
  });
});

describe('ticket location normalization', () => {
  it('normalizes valid coordinates and readable addresses in list responses', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
    vi.stubEnv('VITE_USE_MOCK_DATA', undefined);

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify([
            {
              ...apiTicket,
              location: {
                ...apiTicket.location,
                latitude: 90,
                longitude: 180,
                addressText: '  Beirut waterfront  ',
              },
            },
          ]),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          },
        ),
      ),
    );

    const { fetchTickets } = await import('@/services/tickets');
    const tickets = await fetchTickets();

    expect(tickets[0].location).toEqual({
      latitude: 90,
      longitude: 180,
      addressText: 'Beirut waterfront',
      source: 'GPS',
    });
  });

  it.each([
    ['missing latitude', { longitude: 35.5018, addressText: 'Beirut', source: 'GPS' }],
    [
      'out-of-range latitude',
      { latitude: 91, longitude: 35.5018, addressText: 'Beirut', source: 'GPS' },
    ],
    [
      'string longitude',
      { latitude: 33.8938, longitude: '35.5018', addressText: 'Beirut', source: 'GPS' },
    ],
    ['blank address', { latitude: 33.8938, longitude: 35.5018, addressText: ' ', source: 'GPS' }],
    [
      'unknown source',
      { latitude: 33.8938, longitude: 35.5018, addressText: 'Beirut', source: 'UNKNOWN' },
    ],
  ])('rejects %s instead of substituting a map coordinate', async (_label, location) => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
    vi.stubEnv('VITE_USE_MOCK_DATA', undefined);

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ ...apiTicket, location }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );

    const { fetchTicketById } = await import('@/services/tickets');

    await expect(fetchTicketById('tkt_123')).rejects.toThrow(
      'Unexpected ticket location response shape.',
    );
  });
});

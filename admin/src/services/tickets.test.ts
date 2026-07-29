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
            urgencyScore: 75,
            urgencyReason: 'Critical (75): immediate safety danger.',
          },
          statusHistory: [
            {
              status: 'SUBMITTED',
              changedAt: '2026-07-14T10:00:00Z',
              changedBy: 'system',
            },
            {
              status: 'TOTALLY_INVALID',
              changedAt: '2026-07-14T10:02:00Z',
              changedBy: 'staff-bad',
            },
            {
              status: 'UNDER_REVIEW',
              changedAt: '2026-07-14T10:05:00Z',
              changedBy: 'staff-1',
              note: 'Accepted for review.',
            },
            {
              status: 'RESOLVED',
              changedAt: 'not-a-date',
            },
          ],
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
    expect(updatedTicket?.ai?.urgencyScore).toBe(75);
    expect(updatedTicket?.ai?.urgencyReason).toContain('immediate safety danger');
    expect(updatedTicket?.statusHistory).toEqual([
      {
        status: 'SUBMITTED',
        changedAt: '2026-07-14T10:00:00Z',
        changedBy: 'system',
      },
      {
        status: 'UNDER_REVIEW',
        changedAt: '2026-07-14T10:05:00Z',
        changedBy: 'staff-1',
        note: 'Accepted for review.',
      },
    ]);
  });

  it('preserves critical priorities from the ticket read response shape', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
    vi.stubEnv('VITE_USE_MOCK_DATA', undefined);

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify([{ ...apiTicket, priority: 'critical' }]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );

    const { fetchTickets } = await import('@/services/tickets');
    const tickets = await fetchTickets();

    expect(tickets[0].priority).toBe('critical');
  });

  it('preserves duplicate suggestions from the ticket read response shape', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
    vi.stubEnv('VITE_USE_MOCK_DATA', undefined);

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            ...apiTicket,
            duplicateSuggestions: [
              {
                ticketId: 'tkt_456',
                ticketNumber: 'BG-456',
                distanceMeters: 18.7,
                status: 'IN_PROGRESS',
                category: 'waste',
                score: 0.91,
                categoryMatch: 'same',
              },
            ],
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          },
        ),
      ),
    );

    const { fetchTicketById } = await import('@/services/tickets');
    const ticket = await fetchTicketById('tkt_123');

    expect(ticket?.duplicateSuggestions).toEqual([
      {
        ticketId: 'tkt_456',
        ticketNumber: 'BG-456',
        distanceMeters: 18.7,
        status: 'IN_PROGRESS',
        category: 'waste',
        score: 0.91,
        categoryMatch: 'same',
      },
    ]);
  });
});

describe('reviewTicketCategory', () => {
  it('sends the final category to the real backend and preserves the AI suggestion', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
    vi.stubEnv('VITE_USE_MOCK_DATA', undefined);

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          ...apiTicket,
          category: 'waste',
          ai: {
            aiSuggestedCategory: 'street_lighting',
            aiCategoryExplanation: 'The report describes a broken street light.',
            finalCategory: 'waste',
            categoryReviewedAt: '2026-07-17T08:00:00Z',
            aiProcessingStatus: 'completed',
          },
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const { reviewTicketCategory } = await import('@/services/tickets');
    const updatedTicket = await reviewTicketCategory('tkt_123', {
      finalCategory: 'waste',
    });

    expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/v1/tickets/tkt_123/category', {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ finalCategory: 'waste' }),
    });
    expect(updatedTicket?.category).toBe('waste');
    expect(updatedTicket?.ai?.finalCategory).toBe('waste');
    expect(updatedTicket?.ai?.aiSuggestedCategory).toBe('street_lighting');
  });

  it('surfaces backend validation messages', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
    vi.stubEnv('VITE_USE_MOCK_DATA', undefined);

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              message: 'Request validation failed.',
              details: [{ field: 'finalCategory', message: 'Category is not supported.' }],
            },
          }),
          {
            status: 400,
            headers: { 'Content-Type': 'application/json' },
          },
        ),
      ),
    );

    const { reviewTicketCategory } = await import('@/services/tickets');

    await expect(reviewTicketCategory('tkt_123', { finalCategory: 'invalid' })).rejects.toThrow(
      'Request validation failed. finalCategory: Category is not supported.',
    );
  });
});

describe('mergeDuplicateTickets', () => {
  it('posts the merge to the real backend and normalizes the group response', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
    vi.stubEnv('VITE_USE_MOCK_DATA', undefined);

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          ...apiTicket,
          duplicateGroupId: 'dup_group1',
          duplicateGroup: {
            duplicateGroupId: 'dup_group1',
            ticketIds: ['tkt_123', 'tkt_456'],
            canonicalTicketId: 'tkt_123',
          },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const { mergeDuplicateTickets } = await import('@/services/tickets');
    const merged = await mergeDuplicateTickets({
      canonicalTicketId: 'tkt_123',
      duplicateTicketIds: ['tkt_456'],
    });

    expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/v1/tickets/merge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ canonicalTicketId: 'tkt_123', duplicateTicketIds: ['tkt_456'] }),
    });
    expect(merged?.duplicateGroupId).toBe('dup_group1');
    expect(merged?.duplicateGroup?.ticketIds).toEqual(['tkt_123', 'tkt_456']);
    expect(merged?.duplicateGroup?.canonicalTicketId).toBe('tkt_123');
  });

  it('surfaces backend merge validation errors', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
    vi.stubEnv('VITE_USE_MOCK_DATA', undefined);

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: { message: 'All merged tickets must share the same category.' },
          }),
          { status: 400, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    );

    const { mergeDuplicateTickets } = await import('@/services/tickets');

    await expect(
      mergeDuplicateTickets({ canonicalTicketId: 'tkt_123', duplicateTicketIds: ['tkt_456'] }),
    ).rejects.toThrow('All merged tickets must share the same category.');
  });
});

describe('mergeDuplicateTickets (mock mode)', () => {
  const MOCK_ROAD_MAIN = 'tkt_11111111111111111111111111111111';
  const MOCK_ROAD_DUP = 'tkt_bbbbbbbb444455556666bbbbbbbbbbbb';
  const MOCK_LIGHTING = 'tkt_33333333333333333333333333333333';
  const MOCK_GROUPED_WASTE = 'tkt_22222222222222222222222222222222';

  it('persists the merge for the session on every member ticket', async () => {
    vi.stubEnv('VITE_USE_MOCK_DATA', 'true');

    const { mergeDuplicateTickets, fetchTicketById } = await import('@/services/tickets');
    const merged = await mergeDuplicateTickets({
      canonicalTicketId: MOCK_ROAD_MAIN,
      duplicateTicketIds: [MOCK_ROAD_DUP],
    });

    expect(merged?.duplicateGroupId).toBeTruthy();
    expect(merged?.duplicateGroup?.canonicalTicketId).toBe(MOCK_ROAD_MAIN);

    // The duplicate must reflect the merge on a fresh read, not just the response.
    const duplicate = await fetchTicketById(MOCK_ROAD_DUP);
    expect(duplicate?.duplicateGroupId).toBe(merged?.duplicateGroupId);
    expect(duplicate?.duplicateGroup?.canonicalTicketId).toBe(MOCK_ROAD_MAIN);
    expect(duplicate?.duplicateGroup?.ticketIds).toEqual([MOCK_ROAD_MAIN, MOCK_ROAD_DUP]);
  });

  it('rejects cross-category mock merges like the backend', async () => {
    vi.stubEnv('VITE_USE_MOCK_DATA', 'true');

    const { mergeDuplicateTickets } = await import('@/services/tickets');

    await expect(
      mergeDuplicateTickets({
        canonicalTicketId: MOCK_ROAD_MAIN,
        duplicateTicketIds: [MOCK_LIGHTING],
      }),
    ).rejects.toThrow('All merged tickets must share the same category as the main ticket.');
  });

  it('rejects merging a ticket that already belongs to a group', async () => {
    vi.stubEnv('VITE_USE_MOCK_DATA', 'true');

    const { mergeDuplicateTickets } = await import('@/services/tickets');

    await expect(
      mergeDuplicateTickets({
        canonicalTicketId: MOCK_ROAD_MAIN,
        duplicateTicketIds: [MOCK_GROUPED_WASTE],
      }),
    ).rejects.toThrow('already belongs to a duplicate group');
  });

  it('derives the fixture group canonical from the earliest report instead of hardcoding', async () => {
    vi.stubEnv('VITE_USE_MOCK_DATA', 'true');

    const { fetchTicketById } = await import('@/services/tickets');
    const grouped = await fetchTicketById(MOCK_GROUPED_WASTE);

    // BG-2026-0005 was created before BG-2026-0002, so it is the original report.
    expect(grouped?.duplicateGroup?.canonicalTicketId).toBe('tkt_55555555555555555555555555555555');
    expect(grouped?.duplicateGroup?.ticketIds).toHaveLength(2);
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
    [
      'missing latitude',
      { longitude: 35.5018, addressText: 'Beirut', source: 'GPS' },
      {
        latitude: Number.NaN,
        longitude: 35.5018,
        addressText: 'Beirut',
        source: 'GPS' as const,
      },
    ],
    [
      'out-of-range latitude',
      { latitude: 91, longitude: 35.5018, addressText: 'Beirut', source: 'GPS' },
      {
        latitude: Number.NaN,
        longitude: 35.5018,
        addressText: 'Beirut',
        source: 'GPS' as const,
      },
    ],
    [
      'string longitude',
      { latitude: 33.8938, longitude: '35.5018', addressText: 'Beirut', source: 'GPS' },
      {
        latitude: 33.8938,
        longitude: Number.NaN,
        addressText: 'Beirut',
        source: 'GPS' as const,
      },
    ],
    [
      'blank address',
      { latitude: 33.8938, longitude: 35.5018, addressText: ' ', source: 'GPS' },
      {
        latitude: 33.8938,
        longitude: 35.5018,
        addressText: '',
        source: 'GPS' as const,
      },
    ],
    [
      'unknown source',
      { latitude: 33.8938, longitude: 35.5018, addressText: 'Beirut', source: 'UNKNOWN' },
      {
        latitude: 33.8938,
        longitude: 35.5018,
        addressText: 'Beirut',
        source: 'PLACEHOLDER' as const,
      },
    ],
  ])(
    'keeps the ticket readable when location has %s',
    async (_label, location, expectedLocation) => {
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
      const ticket = await fetchTicketById('tkt_123');

      expect(ticket?.location).toEqual(expectedLocation);
    },
  );

  it('keeps list reads working when one ticket has a malformed location', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
    vi.stubEnv('VITE_USE_MOCK_DATA', undefined);

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify([
            apiTicket,
            {
              ...apiTicket,
              ticketId: 'tkt_bad',
              ticketNumber: 'BG-BAD',
              location: null,
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

    expect(tickets).toHaveLength(2);
    expect(tickets[0].ticketId).toBe('tkt_123');
    expect(tickets[1].ticketId).toBe('tkt_bad');
    expect(Number.isNaN(tickets[1].location.latitude)).toBe(true);
    expect(Number.isNaN(tickets[1].location.longitude)).toBe(true);
    expect(tickets[1].location.addressText).toBe('');
    expect(tickets[1].location.source).toBe('PLACEHOLDER');
  });
});

describe('assignTicketDepartment', () => {
  it('sends the department override to the real backend and preserves the suggestion', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
    vi.stubEnv('VITE_USE_MOCK_DATA', undefined);

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          ...apiTicket,
          departmentId: 'd2222222-2222-2222-2222-222222222222',
          department: {
            departmentId: 'd2222222-2222-2222-2222-222222222222',
            name: 'Waste Management',
          },
          updatedBy: 'staff-1',
          ai: {
            suggestedDepartmentId: 'd1111111-1111-1111-1111-111111111111',
            aiProcessingStatus: 'completed',
          },
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const { assignTicketDepartment } = await import('@/services/tickets');
    const updatedTicket = await assignTicketDepartment('tkt_123', {
      departmentId: 'd2222222-2222-2222-2222-222222222222',
      updatedBy: 'staff-1',
    });

    expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/v1/tickets/tkt_123/department', {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        departmentId: 'd2222222-2222-2222-2222-222222222222',
        updatedBy: 'staff-1',
      }),
    });
    expect(updatedTicket?.departmentId).toBe('d2222222-2222-2222-2222-222222222222');
    expect(updatedTicket?.departmentName).toBe('Waste Management');
    expect(updatedTicket?.ai?.suggestedDepartmentId).toBe('d1111111-1111-1111-1111-111111111111');
    expect(updatedTicket?.updatedBy).toBe('staff-1');
  });

  it('surfaces backend validation messages for unknown departments', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
    vi.stubEnv('VITE_USE_MOCK_DATA', undefined);

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              message: 'Request validation failed.',
              details: [{ field: 'departmentId', message: 'Department is not in the catalog.' }],
            },
          }),
          {
            status: 400,
            headers: { 'Content-Type': 'application/json' },
          },
        ),
      ),
    );

    const { assignTicketDepartment } = await import('@/services/tickets');

    await expect(
      assignTicketDepartment('tkt_123', { departmentId: 'not-a-department' }),
    ).rejects.toThrow('Request validation failed. departmentId: Department is not in the catalog.');
  });
});

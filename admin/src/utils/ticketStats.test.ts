import { describe, expect, it } from 'vitest';

import type { Ticket } from '@/types/ticket';
import { computeTicketStats, filterTickets } from '@/utils/ticketStats';

const baseTicket: Ticket = {
  ticketId: 'tkt_1',
  ticketNumber: 'BG-1',
  trackingCode: 'ABC123',
  description: 'Ticket',
  contact: {},
  location: {
    latitude: 33.89,
    longitude: 35.5,
    addressText: 'Beirut',
    source: 'GPS',
  },
  imageObjectKey: 'reports/tkt_1.jpg',
  status: 'SUBMITTED',
  category: 'road_damage',
  priority: null,
  createdBy: null,
  municipalityId: null,
  departmentId: null,
  duplicateGroupId: null,
  createdAt: '2026-07-17T08:00:00Z',
  updatedAt: '2026-07-17T08:01:00Z',
};

describe('computeTicketStats', () => {
  it('counts high and critical tickets as high urgency', () => {
    const stats = computeTicketStats([
      { ...baseTicket, ticketId: 'tkt_high', priority: 'high' },
      { ...baseTicket, ticketId: 'tkt_critical', priority: 'critical' },
      { ...baseTicket, ticketId: 'tkt_medium', priority: 'medium' },
    ]);

    expect(stats.highUrgency).toBe(2);
  });
});

describe('filterTickets', () => {
  it('combines search, status, category, urgency, and department filters', () => {
    const matching = {
      ...baseTicket,
      ticketId: 'tkt_match',
      ticketNumber: 'BG-35',
      description: 'Overflowing bins near the market.',
      status: 'IN_PROGRESS' as const,
      category: 'waste',
      priority: 'high' as const,
      departmentId: 'd2222222-2222-2222-2222-222222222222',
    };

    const filtered = filterTickets(
      [
        matching,
        {
          ...matching,
          ticketId: 'tkt_wrong_department',
          departmentId: 'd1111111-1111-1111-1111-111111111111',
        },
        { ...matching, ticketId: 'tkt_wrong_urgency', priority: 'low' },
        { ...matching, ticketId: 'tkt_wrong_status', status: 'RESOLVED' },
      ],
      'market',
      'IN_PROGRESS',
      'waste',
      'high',
      'd2222222-2222-2222-2222-222222222222',
    );

    expect(filtered).toEqual([matching]);
  });

  it('returns no matches when persisted urgency or department values are missing', () => {
    const filtered = filterTickets(
      [{ ...baseTicket, priority: null, departmentId: null }],
      '',
      'ALL',
      'ALL',
      'critical',
      'd3333333-3333-3333-3333-333333333333',
    );

    expect(filtered).toEqual([]);
  });
});

import { describe, expect, it } from 'vitest';

import type { Ticket } from '@/types/ticket';
import { computeTicketStats } from '@/utils/ticketStats';

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

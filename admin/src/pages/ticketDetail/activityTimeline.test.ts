import { describe, expect, it } from 'vitest';

import type { Ticket } from '@/types/ticket';
import { buildActivityTimeline, formatAuditAction } from '@/pages/ticketDetail/activityTimeline';

const ticket: Ticket = {
  ticketId: 'tkt_123',
  ticketNumber: 'BG-2026-0001',
  trackingCode: 'ABC123',
  description: 'Pothole',
  contact: {},
  location: {
    latitude: 33.8,
    longitude: 35.5,
    addressText: 'Hamra',
    source: 'GPS',
  },
  imageObjectKey: 'reports/tkt_123.jpg',
  status: 'ASSIGNED',
  category: 'road_damage',
  priority: null,
  createdBy: null,
  municipalityId: null,
  departmentId: null,
  duplicateGroupId: null,
  createdAt: '2026-07-17T08:00:00Z',
  updatedAt: '2026-07-17T08:10:00Z',
  auditHistory: [
    {
      actionType: 'WORK_ORDER_CREATE',
      summary: 'Work order wo_1 created in QUEUED.',
      changedAt: '2026-07-17T08:10:00Z',
      actorId: 'staff_admin_001',
      newValue: 'wo_1',
    },
  ],
};

describe('activity timeline work-order events', () => {
  it('labels work-order audit actions', () => {
    expect(formatAuditAction('WORK_ORDER_CREATE')).toBe('Work order created');
    expect(formatAuditAction('WORK_ORDER_COMPLETE')).toBe('Work order completed');
  });

  it('keeps work-order audit rows on the operational timeline', () => {
    const events = buildActivityTimeline(ticket);
    expect(events.some((event) => event.title === 'Work order created')).toBe(true);
  });
});

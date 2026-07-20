import { describe, expect, it } from 'vitest';

import type { Ticket } from '@/types/ticket';
import { effectiveTicketCategory } from '@/utils/ticketCategory';

function buildTicket(overrides: Partial<Ticket>): Ticket {
  return {
    ticketId: 'tkt_1',
    ticketNumber: 'BG-2026-0001',
    trackingCode: 'AB12CD',
    description: 'Pothole',
    contact: {},
    location: { latitude: 33.89, longitude: 35.5, addressText: 'Beirut', source: 'GPS' },
    imageObjectKey: 'reports/mock/a.jpg',
    status: 'SUBMITTED',
    category: 'PENDING_CLASSIFICATION',
    priority: null,
    createdBy: null,
    municipalityId: null,
    departmentId: null,
    duplicateGroupId: null,
    createdAt: '2026-07-01T00:00:00Z',
    updatedAt: null,
    ...overrides,
  };
}

describe('effectiveTicketCategory', () => {
  it('prefers the staff-reviewed final category', () => {
    const ticket = buildTicket({
      category: 'road_damage',
      ai: { finalCategory: 'waste', aiSuggestedCategory: 'lighting' },
    });
    expect(effectiveTicketCategory(ticket)).toBe('waste');
  });

  it('falls back to the AI suggestion before the stored category', () => {
    const ticket = buildTicket({
      category: 'PENDING_CLASSIFICATION',
      ai: { aiSuggestedCategory: 'road_damage' },
    });
    expect(effectiveTicketCategory(ticket)).toBe('road_damage');
  });

  it('uses the stored category when the ticket is already classified', () => {
    expect(effectiveTicketCategory(buildTicket({ category: 'waste' }))).toBe('waste');
  });

  it('returns null while the ticket is pending classification', () => {
    expect(effectiveTicketCategory(buildTicket({}))).toBeNull();
    expect(
      effectiveTicketCategory(buildTicket({ ai: { aiProcessingStatus: 'pending' } })),
    ).toBeNull();
  });
});

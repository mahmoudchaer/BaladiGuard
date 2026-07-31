import { describe, expect, it } from 'vitest';
import type { Ticket } from '@/types/ticket';
import { getDepartmentSummary } from '@/utils/departmentSummary';

const ticket = (id: string, departmentId: string | null, suggestedDepartmentId?: string): Ticket => ({
  ticketId: id, ticketNumber: id, trackingCode: id, description: '', contact: {},
  location: { latitude: 0, longitude: 0, addressText: '', source: 'MANUAL' }, imageObjectKey: '',
  status: 'SUBMITTED', category: 'waste', priority: null, createdBy: null, municipalityId: null,
  departmentId, duplicateGroupId: null, createdAt: '2026-01-01T00:00:00Z', updatedAt: null,
  ai: suggestedDepartmentId ? { suggestedDepartmentId } : undefined,
});

describe('getDepartmentSummary', () => {
  it('groups assigned and suggested tickets, preferring assigned ownership', () => {
    expect(getDepartmentSummary([
      ticket('1', 'd2222222-2222-2222-2222-222222222222'),
      ticket('2', 'd2222222-2222-2222-2222-222222222222'),
      ticket('3', null, 'd3333333-3333-3333-3333-333333333333'),
      ticket('4', null),
    ])).toMatchObject([
      { name: 'Waste Management', count: 2, assignedCount: 2 },
      { name: 'Street Lighting', count: 1, suggestedCount: 1 },
      { name: 'Unassigned', count: 1, unassigned: true },
    ]);
  });

  it('returns no groups for an empty dataset', () => {
    expect(getDepartmentSummary([])).toEqual([]);
  });
});

import { describe, expect, it } from 'vitest';
import type { Ticket } from '@/types/ticket';
import { getCategoryDistribution } from '@/utils/categoryDistribution';

const ticket = (category: string, id: string): Ticket => ({
  ticketId: id, ticketNumber: id, trackingCode: id, description: '', contact: {},
  location: { latitude: 0, longitude: 0, addressText: '', source: 'MANUAL' }, imageObjectKey: '',
  status: 'SUBMITTED', category, priority: null, createdBy: null, municipalityId: null,
  departmentId: null, duplicateGroupId: null, createdAt: '2026-01-01T00:00:00Z', updatedAt: null,
});

describe('getCategoryDistribution', () => {
  it('returns descending category counts and percentages', () => {
    expect(getCategoryDistribution([
      ticket('waste', '1'), ticket('road_damage', '2'), ticket('waste', '3'), ticket('noise', '4'),
    ])).toEqual([
      { category: 'waste', count: 2, percentage: 50 },
      { category: 'noise', count: 1, percentage: 25 },
      { category: 'road_damage', count: 1, percentage: 25 },
    ]);
  });

  it('returns an empty distribution for an empty dataset', () => {
    expect(getCategoryDistribution([])).toEqual([]);
  });
});

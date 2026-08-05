import React from 'react';
import { beforeEach, vi } from 'vitest';
import { describe, expect, it } from 'vitest';

import PublicReportDetailScreen from '../../app/public/[ticketNumber]';
import { __setSearchParams } from './mocks/expo-router';
import { renderWithProvidersAsync } from './render';

const publicReport = {
  ticketNumber: 'BG-2026-0001',
  status: 'IN_PROGRESS' as const,
  category: 'road_damage',
  description: 'Staff-approved public summary of the road hazard.',
  location: { addressText: 'Hamra, Beirut' },
  mapLocation: {
    addressText: 'Hamra, Beirut',
    latitude: 33.896,
    longitude: 35.478,
  },
  department: { name: 'Road Maintenance' },
  attribution: { displayName: 'Community member', isNamed: false },
  createdAt: '2026-07-07T00:00:00Z',
  updatedAt: '2026-07-07T02:00:00Z',
};

vi.mock('@/services/api/tickets', () => ({
  getPublicTicketByNumber: vi.fn(async () => publicReport),
}));

vi.mock('react-native-maps', () => ({
  default: ({ children, ...props }: { children?: React.ReactNode }) =>
    React.createElement('MapView', props, children),
  Marker: ({ children, ...props }: { children?: React.ReactNode }) =>
    React.createElement('Marker', props, children),
}));

import { getPublicTicketByNumber } from '@/services/api/tickets';

describe('PublicReportDetailScreen', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    __setSearchParams({ ticketNumber: 'BG-2026-0001' });
    vi.mocked(getPublicTicketByNumber).mockResolvedValue(publicReport);
  });

  it('loads a citizen-safe public detail view by ticket number', async () => {
    const screen = await renderWithProvidersAsync(<PublicReportDetailScreen />);

    expect(getPublicTicketByNumber).toHaveBeenCalledWith('BG-2026-0001');
    expect(screen.root.findByProps({ testID: 'public-report-detail' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'BG-2026-0001' })).toBeTruthy();
    expect(
      screen.root.findByProps({
        children: 'Staff-approved public summary of the road hazard.',
      }),
    ).toBeTruthy();
    expect(screen.root.findAll((node) => String(node.type) === 'Marker')).toHaveLength(1);
  });
});

import React from 'react';
import { beforeEach, vi } from 'vitest';
import { describe, expect, it } from 'vitest';

import HomeScreen from '../../app/index';
import { renderWithProvidersAsync } from './render';

const publicTickets = {
  items: [
    {
      ticketNumber: 'BG-2026-0001',
      status: 'IN_PROGRESS' as const,
      category: 'road_damage',
      description: 'Large pothole near the university gate causing traffic disruption.',
      location: { addressText: 'Near AUB Main Gate, Hamra, Beirut' },
      mapLocation: {
        addressText: 'Near AUB Main Gate, Hamra, Beirut',
        latitude: 33.896,
        longitude: 35.478,
      },
      department: { name: 'Road Maintenance' },
      attribution: { displayName: 'Community member', isNamed: false },
      createdAt: '2026-07-07T00:00:00Z',
      updatedAt: '2026-07-07T02:00:00Z',
    },
  ],
  nextCursor: null,
  limit: 20,
};

vi.mock('@/services/api/tickets', () => ({
  getPublicTickets: vi.fn(async () => publicTickets),
}));

vi.mock('react-native-maps', () => ({
  default: ({ children, ...props }: { children?: React.ReactNode }) =>
    React.createElement('MapView', props, children),
  Marker: ({ children, ...props }: { children?: React.ReactNode }) =>
    React.createElement('Marker', props, children),
}));

import { getPublicTickets } from '@/services/api/tickets';

function textContent(value: React.ReactNode): string {
  if (Array.isArray(value)) {
    return value.map(textContent).join('');
  }
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '';
}

function hasTextContaining(
  screen: Awaited<ReturnType<typeof renderWithProvidersAsync>>,
  text: string,
): boolean {
  return screen.root.findAll((node) => textContent(node.props.children).includes(text)).length > 0;
}

describe('HomeScreen', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getPublicTickets).mockResolvedValue(publicTickets);
  });

  it('renders the citizen reporting, tracking, privacy, and sign-in entry points', async () => {
    const screen = await renderWithProvidersAsync(<HomeScreen />);

    expect(screen.root.findByProps({ children: 'BaladiGuard' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Report an issue' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Track a report' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Privacy notice' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Sign in with phone' })).toBeTruthy();
  });

  it('loads and renders the public report feed without auth', async () => {
    const screen = await renderWithProvidersAsync(<HomeScreen />);

    expect(getPublicTickets).toHaveBeenCalledWith({ limit: 20 });
    expect(screen.root.findByProps({ testID: 'public-report-feed' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Public reports' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'BG-2026-0001' })).toBeTruthy();
    expect(
      screen.root.findByProps({
        children: 'Large pothole near the university gate causing traffic disruption.',
      }),
    ).toBeTruthy();
    expect(hasTextContaining(screen, 'Reported by Community member')).toBe(true);
    expect(screen.root.findAll((node) => String(node.type) === 'Marker')).toHaveLength(1);
  });
});

import React from 'react';
import { act } from 'react-test-renderer';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import HomeScreen from '../../app/index';
import ExploreScreen from '../../app/explore';
import { getPublicTickets } from '@/services/api/tickets';
import { __getRouterMockState, __resetExpoRouterMock } from './mocks/expo-router';
import { renderWithProvidersAsync } from './render';

const publicTickets = {
  items: [
    {
      ticketNumber: 'BG-2026-0001',
      status: 'IN_PROGRESS' as const,
      category: 'road_damage',
      description: 'Large pothole near the university gate.',
      location: { addressText: 'Hamra, Beirut' },
      mapLocation: { addressText: 'Hamra, Beirut', latitude: 33.896, longitude: 35.478 },
      attribution: { displayName: 'Community member', isNamed: false },
      photoUrl: null,
      createdAt: '2026-07-07T00:00:00Z',
      updatedAt: '2026-07-07T02:00:00Z',
    },
  ],
  nextCursor: null,
  limit: 20,
};

vi.mock('@/services/api/tickets', () => ({
  getPublicTickets: vi.fn(async () => publicTickets),
  getCitizenTicketHistory: vi.fn(),
}));

describe('mobile entry and Explore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    __resetExpoRouterMock();
    vi.mocked(getPublicTickets).mockResolvedValue(publicTickets);
  });

  it('renders the focused guest welcome and open-access choices', async () => {
    const screen = await renderWithProvidersAsync(<HomeScreen />);
    expect(screen.root.findByProps({ testID: 'welcome-screen' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Sign in or create an account' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Continue as guest' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Track with a code' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Privacy notice' })).toBeTruthy();
    expect(getPublicTickets).not.toHaveBeenCalled();
  });

  it('loads privacy-safe reports in Explore instead of welcome', async () => {
    const screen = await renderWithProvidersAsync(<ExploreScreen />);
    expect(getPublicTickets).toHaveBeenCalledWith({ limit: 20 });
    expect(screen.root.findByProps({ testID: 'public-report-feed' })).toBeTruthy();
    expect(
      screen.root.findByProps({ children: 'Large pothole near the university gate.' }),
    ).toBeTruthy();
    expect(
      screen.root.findByProps({ testID: 'public-report-attribution-BG-2026-0001' }),
    ).toBeTruthy();
  });

  it('opens a public report from Explore', async () => {
    const screen = await renderWithProvidersAsync(<ExploreScreen />);
    await act(async () =>
      screen.root.findByProps({ testID: 'public-report-card-BG-2026-0001' }).props.onPress(),
    );
    expect(__getRouterMockState().pushCalls).toContainEqual({
      pathname: '/public/[ticketNumber]',
      params: { ticketNumber: 'BG-2026-0001' },
    });
  });
});

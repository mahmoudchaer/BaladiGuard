import React from 'react';
import { act } from 'react-test-renderer';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import HomeScreen from '../../app/index';
import { __getRouterMockState, __resetExpoRouterMock } from './mocks/expo-router';
import { renderWithProvidersAsync } from './render';
import type { PublicTicketResponse } from '@/types/ticket';

function makeReport(
  overrides: Partial<PublicTicketResponse> & {
    ticketNumber: string;
    latitude?: number;
    longitude?: number;
  },
): PublicTicketResponse {
  const { latitude = 33.896, longitude = 35.478, ticketNumber, ...rest } = overrides;
  return {
    ticketNumber,
    status: rest.status ?? 'IN_PROGRESS',
    category: rest.category ?? 'road_damage',
    description: rest.description ?? 'Large pothole near the university gate.',
    location: rest.location ?? { addressText: 'Near AUB Main Gate, Hamra, Beirut' },
    mapLocation: {
      addressText: 'Near AUB Main Gate, Hamra, Beirut',
      latitude,
      longitude,
    },
    department: { name: 'Road Maintenance' },
    attribution: { displayName: 'Community member', isNamed: false },
    photoUrl: 'https://example.com/report-photo.jpg',
    createdAt: '2026-07-07T00:00:00Z',
    updatedAt: '2026-07-07T02:00:00Z',
    ...rest,
  };
}

const baseTickets = {
  items: [
    makeReport({ ticketNumber: 'BG-2026-0001', latitude: 33.896, longitude: 35.478 }),
    makeReport({
      ticketNumber: 'BG-2026-0002',
      status: 'RESOLVED',
      category: 'waste',
      latitude: 33.89601,
      longitude: 35.47801,
      description: 'Overflowing bins on Bliss Street.',
    }),
    makeReport({
      ticketNumber: 'BG-2026-0003',
      category: 'street_lighting',
      latitude: Number.NaN,
      longitude: 35.48,
      description: 'Broken lamp without valid map pin.',
    }),
  ],
  nextCursor: null,
  limit: 50,
};

const denseTickets = {
  items: Array.from({ length: 24 }, (_, index) =>
    makeReport({
      ticketNumber: `BG-DENSE-${String(index).padStart(2, '0')}`,
      latitude: 33.9 + (index % 3) * 0.00002,
      longitude: 35.5 + Math.floor(index / 3) * 0.00002,
      description: `Dense fixture report ${index}`,
    }),
  ),
  nextCursor: null,
  limit: 50,
};

vi.mock('@/services/api/tickets', () => ({
  getPublicTickets: vi.fn(async () => baseTickets),
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

async function flush() {
  for (let i = 0; i < 5; i += 1) {
    await act(async () => {
      await Promise.resolve();
    });
  }
}

describe('HomeScreen public map clustering', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    __resetExpoRouterMock();
    vi.mocked(getPublicTickets).mockResolvedValue(baseTickets);
  });

  it('renders entry points and the public list alternative', async () => {
    const screen = await renderWithProvidersAsync(<HomeScreen />);
    await flush();

    expect(screen.root.findByProps({ children: 'BaladiGuard' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Report an issue' })).toBeTruthy();
    expect(screen.root.findByProps({ testID: 'public-report-list' })).toBeTruthy();
    expect(screen.root.findByProps({ testID: 'public-map-list-hint' })).toBeTruthy();
  });

  it('loads public tickets and shows list cards without auth', async () => {
    const screen = await renderWithProvidersAsync(<HomeScreen />);
    await flush();

    expect(getPublicTickets).toHaveBeenCalledWith({
      limit: 50,
      signal: expect.any(AbortSignal),
    });
    expect(screen.root.findByProps({ testID: 'public-report-feed' })).toBeTruthy();
    expect(screen.root.findByProps({ testID: 'public-report-card-BG-2026-0001' })).toBeTruthy();
    expect(hasTextContaining(screen, 'Reported by Community member')).toBe(true);
  });

  it('opens public report details from a card and a single map marker', async () => {
    // Use spread-out singles at high zoom by default region; force isolated points
    vi.mocked(getPublicTickets).mockResolvedValue({
      items: [
        makeReport({ ticketNumber: 'BG-2026-0001', latitude: 33.8, longitude: 35.4 }),
        makeReport({
          ticketNumber: 'BG-2026-0002',
          latitude: 33.95,
          longitude: 35.55,
          status: 'RESOLVED',
          category: 'waste',
        }),
      ],
      nextCursor: null,
      limit: 50,
    });
    const screen = await renderWithProvidersAsync(<HomeScreen />);
    await flush();

    await act(async () => {
      screen.root.findByProps({ testID: 'public-report-card-BG-2026-0001' }).props.onPress();
    });
    expect(__getRouterMockState().pushCalls).toContainEqual({
      pathname: '/public/[ticketNumber]',
      params: { ticketNumber: 'BG-2026-0001' },
    });

    const marker = screen.root.findByProps({ testID: 'public-map-marker-BG-2026-0001' });
    await act(async () => {
      marker.props.onPress();
    });
    expect(__getRouterMockState().pushCalls).toContainEqual({
      pathname: '/public/[ticketNumber]',
      params: { ticketNumber: 'BG-2026-0001' },
    });
  });

  it('shows clustering for dense fixtures and expands on cluster press', async () => {
    vi.mocked(getPublicTickets).mockResolvedValue(denseTickets);
    const screen = await renderWithProvidersAsync(<HomeScreen />);
    await flush();

    const map = screen.root.findByProps({ testID: 'public-map-view' });
    // Zoomed-out region keeps dense points clustered.
    await act(async () => {
      map.props.onRegionChangeComplete?.({
        latitude: 33.9,
        longitude: 35.5,
        latitudeDelta: 0.08,
        longitudeDelta: 0.08,
      });
    });
    await flush();

    const clusters = screen.root.findAll(
      (node) =>
        typeof node.props?.testID === 'string' &&
        node.props.testID.startsWith('public-map-cluster-'),
    );
    expect(clusters.length).toBeGreaterThan(0);

    const firstCluster = clusters.find((node) => typeof node.props.onPress === 'function');
    expect(firstCluster).toBeTruthy();
    await act(async () => {
      firstCluster?.props.onPress();
    });
    await flush();
    // After expand, maps still render and list remains available.
    expect(screen.root.findByProps({ testID: 'public-report-list' })).toBeTruthy();
  });

  it('updates map and list consistently when status filter changes', async () => {
    const screen = await renderWithProvidersAsync(<HomeScreen />);
    await flush();

    expect(screen.root.findByProps({ testID: 'public-report-card-BG-2026-0001' })).toBeTruthy();
    expect(screen.root.findByProps({ testID: 'public-report-card-BG-2026-0002' })).toBeTruthy();

    await act(async () => {
      screen.root.findByProps({ testID: 'public-filter-status-RESOLVED' }).props.onPress();
    });
    await flush();

    expect(screen.root.findByProps({ testID: 'public-report-card-BG-2026-0002' })).toBeTruthy();
    expect(() =>
      screen.root.findByProps({ testID: 'public-report-card-BG-2026-0001' }),
    ).toThrow();
  });

  it('reports incomplete coordinates through partial-data UX while keeping the list', async () => {
    const screen = await renderWithProvidersAsync(<HomeScreen />);
    await flush();

    expect(screen.root.findByProps({ testID: 'public-map-partial-data' })).toBeTruthy();
    expect(screen.root.findByProps({ testID: 'public-report-card-BG-2026-0003' })).toBeTruthy();
  });

  it('shows an empty filter state when no public reports match', async () => {
    const screen = await renderWithProvidersAsync(<HomeScreen />);
    await flush();

    await act(async () => {
      screen.root.findByProps({ testID: 'public-filter-status-CLOSED' }).props.onPress();
    });
    await flush();

    expect(screen.root.findByProps({ testID: 'public-filter-empty' })).toBeTruthy();
    await act(async () => {
      screen.root.findByProps({ testID: 'public-filter-clear' }).props.onPress();
    });
    await flush();
    expect(screen.root.findByProps({ testID: 'public-report-card-BG-2026-0001' })).toBeTruthy();
  });
});

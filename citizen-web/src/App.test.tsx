import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AppRoutes } from '@/App';
import type { PublicTicketMapViewportResponse, PublicTicketResponse } from '@/types/ticket';

const sample: PublicTicketResponse = {
  ticketNumber: 'BG-100001',
  status: 'IN_PROGRESS',
  category: 'road_damage',
  description: 'Large pothole near campus gate.',
  location: { addressText: 'Near AUB Main Gate, Beirut' },
  mapLocation: {
    addressText: 'Near AUB Main Gate, Beirut',
    latitude: 33.9,
    longitude: 35.482,
  },
  department: { name: 'Roads' },
  attribution: { displayName: 'Community member', isNamed: false },
  photoUrl: null,
  createdAt: '2026-08-01T10:00:00Z',
  updatedAt: '2026-08-02T12:00:00Z',
};

vi.mock('@/services/tickets', async () => {
  const actual = await vi.importActual<typeof import('@/services/tickets')>('@/services/tickets');
  return {
    ...actual,
    getPublicTickets: vi.fn(),
    getPublicMapViewport: vi.fn(),
    getPublicTicketByNumber: vi.fn(),
    getTicketByTrackingCode: vi.fn(),
  };
});

vi.mock('@/components/PublicReportsMap', () => ({
  PublicReportsMap: ({
    data,
    onViewportChange,
  }: {
    data: PublicTicketMapViewportResponse | null;
    onViewportChange: (viewport: {
      north: number;
      south: number;
      east: number;
      west: number;
      zoom: number;
    }) => void;
  }) => (
    <button
      data-testid="public-map"
      onClick={() => onViewportChange({ north: 34, south: 33, east: 36, west: 35, zoom: 15 })}
    >
      Map with {data?.markers.length ?? 0} reports
    </button>
  ),
}));

import {
  getPublicTicketByNumber,
  getPublicMapViewport,
  getPublicTickets,
  getTicketByTrackingCode,
} from '@/services/tickets';

function renderApp(path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe('citizen web public browsing', () => {
  beforeEach(() => {
    vi.mocked(getPublicTickets).mockResolvedValue({
      items: [sample],
      nextCursor: 'next-1',
      limit: 20,
    });
    vi.mocked(getPublicTicketByNumber).mockResolvedValue(sample);
    vi.mocked(getPublicMapViewport).mockResolvedValue({
      markers: [
        {
          ticketNumber: sample.ticketNumber,
          status: sample.status,
          category: sample.category,
          addressText: sample.mapLocation.addressText,
          latitude: sample.mapLocation.latitude,
          longitude: sample.mapLocation.longitude,
        },
      ],
      clusters: [],
      limit: 200,
      truncated: false,
      zoom: 15,
    });
    vi.mocked(getTicketByTrackingCode).mockResolvedValue({
      ticketNumber: 'BG-100001',
      trackingCode: 'ABC234',
      status: 'IN_PROGRESS',
      category: 'road_damage',
      location: { addressText: 'Near AUB Main Gate, Beirut' },
      department: { name: 'Roads' },
      createdAt: '2026-08-01T10:00:00Z',
      updatedAt: '2026-08-02T12:00:00Z',
      lastUpdatedAt: '2026-08-02T12:00:00Z',
      timeline: [{ status: 'SUBMITTED', changedAt: '2026-08-01T10:00:00Z' }],
    });
  });

  it('keeps the landing page separate and does not fetch the report directory', async () => {
    renderApp('/');
    expect(screen.getByRole('heading', { name: /Your city,.*within reach\./ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Browse public reports →' })).toHaveAttribute(
      'href',
      '/reports',
    );
    expect(getPublicTickets).not.toHaveBeenCalled();
  });

  it('renders responsive navigation and public list with pagination', async () => {
    const user = userEvent.setup();
    renderApp('/reports');

    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument();
    expect(await screen.findByTestId('public-report-list')).toBeInTheDocument();
    expect(screen.getByText('BG-100001')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Next →' }));
    await waitFor(() => {
      expect(getPublicTickets).toHaveBeenCalledWith(expect.objectContaining({ cursor: 'next-1' }));
    });

    await user.type(screen.getByLabelText('Search public reports'), 'pothole');
    await user.selectOptions(screen.getByLabelText('Filter by status'), 'IN_PROGRESS');
    await waitFor(() => {
      expect(getPublicTickets).toHaveBeenCalledWith(
        expect.objectContaining({ q: 'pothole', status: 'IN_PROGRESS', cursor: null }),
      );
    });
  });

  it('opens public detail from the list', async () => {
    const user = userEvent.setup();
    renderApp('/reports');
    await user.click(await screen.findByRole('link', { name: /BG-100001/i }));
    expect(await screen.findByTestId('public-detail')).toBeInTheDocument();
    expect(getPublicTicketByNumber).toHaveBeenCalledWith('BG-100001');
  });

  it('loads only the visible map viewport', async () => {
    const user = userEvent.setup();
    renderApp('/map');
    await user.click(await screen.findByTestId('public-map'));
    await waitFor(() => expect(getPublicMapViewport).toHaveBeenCalledTimes(1));
    expect(getPublicTickets).not.toHaveBeenCalled();
    expect(screen.getByRole('link', { name: 'View as list' })).toHaveAttribute('href', '/reports');
  });

  it('renders a not-found page for unknown routes', async () => {
    renderApp('/this-route-does-not-exist');
    expect(await screen.findByTestId('not-found-page')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Browse public reports' })).toHaveAttribute(
      'href',
      '/reports',
    );
  });

  it('tracks by code with fixed wording paths', async () => {
    const user = userEvent.setup();
    renderApp('/track');
    await user.type(screen.getByLabelText('Tracking code'), 'ABC234');
    await user.click(screen.getByRole('button', { name: 'Look up' }));
    expect(await screen.findByTestId('track-result')).toBeInTheDocument();
    expect(screen.getByText(/Tracking code: ABC234/)).toBeInTheDocument();
  });

  it('lets a guest prepare a report before phone verification', async () => {
    renderApp('/report');
    expect(
      await screen.findByRole('heading', { name: 'What needs attention?' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Sign in at submit')).toBeInTheDocument();
  });

  it('exposes privacy copy and stub protected routes', async () => {
    const { cleanup } = await import('@testing-library/react');
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          id: 'privacy',
          title: 'Privacy Policy',
          version: '2026-08-22',
          updatedAt: '2026-08-22T00:00:00Z',
          lang: 'en',
          markdown: '# Privacy Policy\n\nCitizen data handling details.',
        }),
        { status: 200 },
      ),
    );
    renderApp('/privacy');
    expect(await screen.findByRole('heading', { name: 'Privacy' })).toBeInTheDocument();
    expect(screen.getByText(/citizen-safe projection/i)).toBeInTheDocument();
    cleanup();

    renderApp('/login');
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });
});

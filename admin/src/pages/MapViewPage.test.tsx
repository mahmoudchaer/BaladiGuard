import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchTicketMapViewport } from '@/services/tickets';
import { renderWithProviders } from '@/test/render';
import type { TicketMapMarker, TicketMapViewport } from '@/types/ticketCollection';
import { MapViewPage } from '@/pages/MapViewPage';

vi.mock('@/services/tickets', () => ({
  fetchTicketMapViewport: vi.fn(),
}));

vi.mock('@/components/TicketMap', () => ({
  TicketMap: ({
    markers,
    clusters,
  }: {
    markers: TicketMapMarker[];
    clusters: { id: string; count: number }[];
  }) => (
    <div data-testid="ticket-map">
      Map with {markers.length} pins · {clusters.length} clusters
    </div>
  ),
}));

const baseMarker: TicketMapMarker = {
  ticketId: 'tkt_123',
  ticketNumber: 'BG-2026-0001',
  status: 'UNDER_REVIEW',
  priority: null,
  latitude: 33.896,
  longitude: 35.478,
  category: 'road_damage',
};

function viewportFromMarkers(markers: TicketMapMarker[]): TicketMapViewport {
  return {
    markers,
    clusters: [],
    limit: 200,
    truncated: false,
    zoom: 14,
  };
}

function renderPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/map" element={<MapViewPage />} />
    </Routes>,
    { route: '/map' },
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('MapViewPage', () => {
  it('shows a loading state while tickets are fetched', () => {
    vi.mocked(fetchTicketMapViewport).mockReturnValue(new Promise(() => undefined));
    renderPage();
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('shows an error state when ticket loading fails', async () => {
    vi.mocked(fetchTicketMapViewport).mockRejectedValue(new Error('Network down'));
    renderPage();

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Network down')).toBeInTheDocument();
  });

  it('renders the map with plottable ticket pins', async () => {
    vi.mocked(fetchTicketMapViewport).mockResolvedValue(viewportFromMarkers([baseMarker]));
    renderPage();

    expect(await screen.findByTestId('ticket-map')).toHaveTextContent('Map with 1 pins');
    expect(screen.getByText('1 pins')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Map View' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Tickets in view' })).toBeInTheDocument();
    expect(screen.getByText('BG-2026-0001')).toBeInTheDocument();
  });

  it('keeps the map visible while filter results refresh', async () => {
    const user = userEvent.setup();
    let resolveFiltered: (value: TicketMapViewport) => void = () => undefined;
    vi.mocked(fetchTicketMapViewport)
      .mockResolvedValueOnce(viewportFromMarkers([baseMarker]))
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveFiltered = resolve;
        }),
      );
    renderPage();

    expect(await screen.findByTestId('ticket-map')).toHaveTextContent('Map with 1 pins');
    await user.click(screen.getByRole('button', { name: 'Resolved' }));

    expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
    expect(screen.getByText('Updating...')).toBeInTheDocument();
    expect(screen.getByTestId('ticket-map')).toHaveTextContent('Map with 1 pins');

    resolveFiltered(viewportFromMarkers([]));
    await waitFor(() => expect(screen.queryByText('Updating...')).not.toBeInTheDocument());
  });

  it('shows a filtered empty state when the server returns no filtered tickets', async () => {
    const user = userEvent.setup();
    vi.mocked(fetchTicketMapViewport)
      .mockResolvedValueOnce(viewportFromMarkers([baseMarker]))
      .mockResolvedValueOnce(viewportFromMarkers([]));
    renderPage();

    expect(await screen.findByTestId('ticket-map')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Resolved' }));

    await waitFor(() => expect(fetchTicketMapViewport).toHaveBeenCalledTimes(2));
    expect(screen.getByText('No matching tickets')).toBeInTheDocument();
  });

  it('renders cluster summary when the viewport returns clusters', async () => {
    vi.mocked(fetchTicketMapViewport).mockResolvedValue({
      markers: [],
      clusters: [{ id: 'c1', latitude: 33.89, longitude: 35.5, count: 12 }],
      limit: 200,
      truncated: false,
      zoom: 11,
    });
    renderPage();

    expect(await screen.findByTestId('ticket-map')).toHaveTextContent('1 clusters');
    expect(screen.getByText(/1 clusters · ~12 reports/)).toBeInTheDocument();
    expect(screen.getByText(/Zoom into a cluster/)).toBeInTheDocument();
  });
});

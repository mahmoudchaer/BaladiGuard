import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { setLocale, t } from '@/i18n';

import { queryStaffAssistant } from '@/services/staffAssistant';
import { fetchTicketMapViewport } from '@/services/tickets';
import { renderWithProviders } from '@/test/render';
import type { StaffAssistantResponse } from '@/types/staffAssistant';
import type { TicketMapMarker, TicketMapViewport } from '@/types/ticketCollection';
import { MapViewPage } from '@/pages/MapViewPage';

vi.mock('@/services/staffAssistant', () => ({
  queryStaffAssistant: vi.fn(),
}));

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

  it('localizes map headings and list chrome for Arabic and French', async () => {
    vi.mocked(fetchTicketMapViewport).mockResolvedValue(viewportFromMarkers([baseMarker]));
    renderPage();
    expect(await screen.findByRole('heading', { name: 'Map View' })).toBeInTheDocument();

    await act(async () => {
      setLocale('ar');
    });
    expect(screen.getByRole('heading', { name: t('map.title') })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: t('map.listTitle') })).toBeInTheDocument();

    await act(async () => {
      setLocale('fr');
    });
    expect(screen.getByRole('heading', { name: t('map.title') })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: t('map.listTitle') })).toBeInTheDocument();
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

  it('applies assistant map filters when already on the map route', async () => {
    const answer: StaffAssistantResponse = {
      intent: 'high_priority_summary',
      asOf: '2026-08-15T12:00:00Z',
      message: '2 accessible high-priority or critical ticket(s).',
      count: 2,
      categories: {},
      statuses: {},
      departments: {},
      areas: {},
      areaClusters: [
        {
          cellId: 'c1',
          south: 33.81,
          west: 35.41,
          north: 33.91,
          east: 35.51,
          label: 'Hamra',
          ticketCount: 2,
          distinctReportCount: 2,
          duplicateGroupCount: 0,
          separateReportCount: 2,
          categories: {},
          ticketIds: ['tkt_123'],
          ticketIdsTruncated: false,
        },
      ],
      areaClusterTotal: 1,
      areaClustersTruncated: false,
      unlocatedCount: 0,
      incompleteCount: 0,
      tickets: [],
      appliedFilters: { urgency: 'high,critical', openOnly: 'true' },
    };
    vi.mocked(queryStaffAssistant).mockResolvedValue(answer);
    vi.mocked(fetchTicketMapViewport).mockResolvedValue(viewportFromMarkers([baseMarker]));
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByTestId('ticket-map')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Assistant' }));
    await user.click(screen.getByRole('button', { name: 'Show high-priority tickets' }));
    const mapActions = await screen.findAllByRole('button', { name: 'View on map' });
    await user.click(mapActions[0]);

    await waitFor(() =>
      expect(fetchTicketMapViewport).toHaveBeenCalledWith(
        expect.objectContaining({
          filters: expect.objectContaining({
            urgency: 'high,critical',
            openOnly: true,
          }),
        }),
      ),
    );
    expect(window.location.pathname).toBe('/map');
    expect(window.location.search).toContain('urgency=high%2Ccritical');
    expect(window.location.search).toContain('openOnly=true');
  });

  it('applies assistant cluster bounds when already on the map route', async () => {
    const answer: StaffAssistantResponse = {
      intent: 'repeated_area_summary',
      asOf: '2026-08-15T12:00:00Z',
      message: 'Repeated problems in 1 area.',
      count: 2,
      categories: {},
      statuses: {},
      departments: {},
      areas: {},
      areaClusters: [
        {
          cellId: 'c1',
          south: 33.81,
          west: 35.41,
          north: 33.91,
          east: 35.51,
          label: 'Hamra',
          ticketCount: 2,
          distinctReportCount: 2,
          duplicateGroupCount: 0,
          separateReportCount: 2,
          categories: {},
          ticketIds: ['tkt_123'],
          ticketIdsTruncated: false,
        },
      ],
      areaClusterTotal: 1,
      areaClustersTruncated: false,
      unlocatedCount: 0,
      incompleteCount: 0,
      tickets: [],
      appliedFilters: { openOnly: 'true' },
    };
    vi.mocked(queryStaffAssistant).mockResolvedValue(answer);
    vi.mocked(fetchTicketMapViewport).mockResolvedValue(viewportFromMarkers([baseMarker]));
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByTestId('ticket-map')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Assistant' }));
    await user.click(screen.getByRole('button', { name: 'Where are repeated problems?' }));
    const mapButtons = await screen.findAllByRole('button', { name: 'View on map' });
    await user.click(mapButtons[1]);

    await waitFor(() =>
      expect(fetchTicketMapViewport).toHaveBeenCalledWith(
        expect.objectContaining({
          south: 33.81,
          west: 35.41,
          north: 33.91,
          east: 35.51,
          filters: expect.objectContaining({
            openOnly: true,
          }),
        }),
      ),
    );
    expect(window.location.search).toContain('south=33.81');
    expect(window.location.search).toContain('openOnly=true');
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

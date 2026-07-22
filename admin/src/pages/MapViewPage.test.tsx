import { screen, waitFor } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchTickets } from '@/services/tickets';
import { renderWithProviders } from '@/test/render';
import type { Ticket } from '@/types/ticket';
import { MapViewPage } from '@/pages/MapViewPage';

vi.mock('@/services/tickets', () => ({
  fetchTickets: vi.fn(),
}));

vi.mock('@/components/TicketMap', () => ({
  TicketMap: ({ tickets }: { tickets: Ticket[] }) => (
    <div data-testid="ticket-map">Map with {tickets.length} pins</div>
  ),
}));

const baseTicket: Ticket = {
  ticketId: 'tkt_123',
  ticketNumber: 'BG-2026-0001',
  trackingCode: 'ABC123',
  description: 'Large pothole near the university gate.',
  contact: {},
  location: {
    latitude: 33.896,
    longitude: 35.478,
    addressText: 'Hamra, Beirut',
    source: 'GPS',
  },
  imageObjectKey: 'reports/tkt_123.jpg',
  status: 'UNDER_REVIEW',
  category: 'road_damage',
  priority: null,
  createdBy: null,
  municipalityId: null,
  departmentId: null,
  duplicateGroupId: null,
  createdAt: '2026-07-17T08:00:00Z',
  updatedAt: '2026-07-17T08:01:00Z',
};

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
    vi.mocked(fetchTickets).mockReturnValue(new Promise(() => undefined));
    renderPage();
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('shows an error state when ticket loading fails', async () => {
    vi.mocked(fetchTickets).mockRejectedValue(new Error('Network down'));
    renderPage();

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Network down')).toBeInTheDocument();
  });

  it('renders the map with plottable ticket pins', async () => {
    vi.mocked(fetchTickets).mockResolvedValue([baseTicket]);
    renderPage();

    expect(await screen.findByTestId('ticket-map')).toHaveTextContent('Map with 1 pins');
    expect(screen.getByText('1 pins')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Map View' })).toBeInTheDocument();
  });

  it('handles tickets without valid coordinates', async () => {
    vi.mocked(fetchTickets).mockResolvedValue([
      {
        ...baseTicket,
        location: {
          latitude: Number.NaN,
          longitude: 35.5,
          addressText: 'Unknown',
          source: 'PLACEHOLDER',
        },
      },
    ]);
    renderPage();

    expect(await screen.findByText('No tickets with valid coordinates')).toBeInTheDocument();
    expect(screen.queryByTestId('ticket-map')).not.toBeInTheDocument();
  });

  it('reports skipped tickets when some coordinates are invalid', async () => {
    vi.mocked(fetchTickets).mockResolvedValue([
      baseTicket,
      {
        ...baseTicket,
        ticketId: 'tkt_bad',
        ticketNumber: 'BG-2026-0002',
        location: {
          latitude: 999,
          longitude: 35.5,
          addressText: 'Invalid',
          source: 'MANUAL',
        },
      },
    ]);
    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId('ticket-map')).toBeInTheDocument();
    });
    expect(screen.getByText('1 pins · 1 without coordinates')).toBeInTheDocument();
  });
});

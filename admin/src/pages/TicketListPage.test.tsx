import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TicketListPage } from '@/pages/TicketListPage';
import { fetchTickets } from '@/services/tickets';
import { renderWithProviders } from '@/test/render';
import type { Ticket } from '@/types/ticket';

vi.mock('@/services/tickets', () => ({
  fetchTickets: vi.fn(),
}));

const tickets: Ticket[] = [
  {
    ticketId: 'tkt_road',
    ticketNumber: 'BG-2026-0001',
    trackingCode: 'ROAD01',
    description: 'Large pothole near the university gate.',
    contact: {},
    location: {
      latitude: 33.896,
      longitude: 35.478,
      addressText: 'Hamra, Beirut',
      source: 'GPS',
    },
    imageObjectKey: 'reports/road.jpg',
    status: 'IN_PROGRESS',
    category: 'road_damage',
    priority: 'high',
    createdBy: null,
    municipalityId: null,
    departmentId: null,
    duplicateGroupId: null,
    createdAt: '2026-07-17T08:00:00Z',
    updatedAt: '2026-07-17T08:01:00Z',
  },
  {
    ticketId: 'tkt_waste',
    ticketNumber: 'BG-2026-0002',
    trackingCode: 'WASTE2',
    description: 'Overflowing garbage bins blocking the sidewalk.',
    contact: {},
    location: {
      latitude: 33.894,
      longitude: 35.502,
      addressText: 'Downtown Beirut',
      source: 'MANUAL',
    },
    imageObjectKey: 'reports/waste.jpg',
    status: 'RESOLVED',
    category: 'waste',
    priority: 'medium',
    createdBy: null,
    municipalityId: null,
    departmentId: null,
    duplicateGroupId: null,
    createdAt: '2026-07-16T08:00:00Z',
    updatedAt: '2026-07-16T10:01:00Z',
  },
];

describe('TicketListPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchTickets).mockResolvedValue(tickets);
  });

  it('shows a loading state while tickets are being fetched', () => {
    vi.mocked(fetchTickets).mockReturnValue(new Promise(() => undefined));

    renderWithProviders(<TicketListPage />);

    expect(screen.getByText('Loading tickets…')).toBeInTheDocument();
  });

  it('renders dashboard stats and ticket rows after a successful load', async () => {
    renderWithProviders(<TicketListPage />);

    expect(await screen.findByText('BG-2026-0001')).toBeInTheDocument();
    expect(screen.getByText('ROAD01')).toBeInTheDocument();
    expect(screen.getByText('Hamra, Beirut')).toBeInTheDocument();
    expect(screen.getByText('BG-2026-0002')).toBeInTheDocument();
    expect(screen.getByText('Downtown Beirut')).toBeInTheDocument();
    expect(screen.getByText('Total Tickets')).toBeInTheDocument();
    expect(screen.getByText('Open Tickets')).toBeInTheDocument();
    expect(screen.getByText('High Urgency')).toBeInTheDocument();
    expect(screen.getAllByText('Resolved').length).toBeGreaterThan(0);
  });

  it('filters the rendered ticket list by search text', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0001');
    await user.type(screen.getByLabelText('Search tickets'), 'WASTE2');

    expect(screen.queryByText('BG-2026-0001')).not.toBeInTheDocument();
    expect(screen.getByText('BG-2026-0002')).toBeInTheDocument();
  });

  it('shows an empty state when the dashboard has no tickets', async () => {
    vi.mocked(fetchTickets).mockResolvedValue([]);

    renderWithProviders(<TicketListPage />);

    expect(await screen.findByText('No tickets yet')).toBeInTheDocument();
    expect(
      screen.getByText('Submitted citizen reports will appear here once they are available.'),
    ).toBeInTheDocument();
  });

  it('shows a failure state when tickets cannot be loaded', async () => {
    vi.mocked(fetchTickets).mockRejectedValue(new Error('Unable to reach backend.'));

    renderWithProviders(<TicketListPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load tickets');
    expect(screen.getByText('Unable to reach backend.')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText('Loading tickets…')).not.toBeInTheDocument());
  });
});

import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TicketListPage } from '@/pages/TicketListPage';
import { fetchTickets } from '@/services/tickets';
import { renderWithProviders } from '@/test/render';
import type { Ticket } from '@/types/ticket';

vi.mock('@/services/tickets', () => ({
  fetchTickets: vi.fn(),
}));

type FetchTicketsTestFilters = Parameters<typeof fetchTickets>[0];

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
    departmentId: 'd1111111-1111-1111-1111-111111111111',
    departmentName: 'Road Maintenance',
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
    departmentId: 'd2222222-2222-2222-2222-222222222222',
    departmentName: 'Waste Management',
    duplicateGroupId: null,
    createdAt: '2026-07-16T08:00:00Z',
    updatedAt: '2026-07-16T10:01:00Z',
  },
];

function applyFetchFilters(items: Ticket[], filters: FetchTicketsTestFilters = {}) {
  return items.filter((ticket) => {
    if (filters.status && filters.status !== 'ALL' && ticket.status !== filters.status) {
      return false;
    }
    if (filters.category && filters.category !== 'ALL' && ticket.category !== filters.category) {
      return false;
    }
    if (filters.urgency && filters.urgency !== 'ALL' && ticket.priority !== filters.urgency) {
      return false;
    }
    if (
      filters.departmentId &&
      filters.departmentId !== 'ALL' &&
      ticket.departmentId !== filters.departmentId
    ) {
      return false;
    }
    return true;
  });
}

describe('TicketListPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchTickets).mockImplementation(async (filters) =>
      applyFetchFilters(tickets, filters),
    );
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
    const stats = within(screen.getByRole('group', { name: 'Ticket summary' }));
    expect(stats.getByText('Total Tickets').previousElementSibling).toHaveTextContent('2');
    expect(stats.getByText('Open Tickets').previousElementSibling).toHaveTextContent('1');
    expect(stats.getByText('High Urgency').previousElementSibling).toHaveTextContent('1');
    expect(stats.getByText('Completed Tickets').previousElementSibling).toHaveTextContent('1');
  });

  it('filters the rendered ticket list by search text', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0001');
    await user.type(screen.getByLabelText('Search tickets'), 'WASTE2');

    expect(screen.queryByText('BG-2026-0001')).not.toBeInTheDocument();
    expect(screen.getByText('BG-2026-0002')).toBeInTheDocument();
  });

  it('filters the rendered ticket list by status', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0001');
    await user.click(screen.getByRole('button', { name: 'Resolved' }));

    await waitFor(() =>
      expect(fetchTickets).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: 'RESOLVED' }),
      ),
    );
    expect(screen.queryByText('BG-2026-0001')).not.toBeInTheDocument();
    expect(screen.getByText('BG-2026-0002')).toBeInTheDocument();
    expect(screen.getByText(/Showing/)).toHaveTextContent('Showing 1 of 2 tickets');
  });

  it('keeps the dashboard visible while filter results refresh', async () => {
    const user = userEvent.setup();
    let resolveFilteredTickets: (value: Ticket[]) => void = () => undefined;
    vi.mocked(fetchTickets)
      .mockResolvedValueOnce(tickets)
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveFilteredTickets = resolve;
        }),
      );

    renderWithProviders(<TicketListPage />);

    expect(await screen.findByText('BG-2026-0001')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Resolved' }));

    expect(screen.queryByText('Loading tickets…')).not.toBeInTheDocument();
    expect(screen.getByText('Updating...')).toBeInTheDocument();
    expect(screen.getByText('BG-2026-0002')).toBeInTheDocument();

    resolveFilteredTickets([tickets[1]]);
    await waitFor(() => expect(screen.queryByText('Updating...')).not.toBeInTheDocument());
  });

  it('filters the rendered ticket list by category', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0001');
    await user.selectOptions(screen.getByLabelText('Category'), 'waste');

    await waitFor(() =>
      expect(fetchTickets).toHaveBeenLastCalledWith(expect.objectContaining({ category: 'waste' })),
    );
    expect(screen.queryByText('BG-2026-0001')).not.toBeInTheDocument();
    expect(screen.getByText('BG-2026-0002')).toBeInTheDocument();
    expect(screen.getByText(/Showing/)).toHaveTextContent('Showing 1 of 2 tickets');
  });

  it('filters the rendered ticket list by urgency', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0001');
    await user.selectOptions(screen.getByLabelText('Urgency'), 'high');

    await waitFor(() =>
      expect(fetchTickets).toHaveBeenLastCalledWith(expect.objectContaining({ urgency: 'high' })),
    );
    expect(screen.getByText('BG-2026-0001')).toBeInTheDocument();
    expect(screen.queryByText('BG-2026-0002')).not.toBeInTheDocument();
    expect(screen.getByText(/Showing/)).toHaveTextContent('Showing 1 of 2 tickets');
  });

  it('filters the rendered ticket list by department', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0001');
    await user.selectOptions(
      screen.getByLabelText('Department'),
      'd2222222-2222-2222-2222-222222222222',
    );

    await waitFor(() =>
      expect(fetchTickets).toHaveBeenLastCalledWith(
        expect.objectContaining({ departmentId: 'd2222222-2222-2222-2222-222222222222' }),
      ),
    );
    expect(screen.queryByText('BG-2026-0001')).not.toBeInTheDocument();
    expect(screen.getByText('BG-2026-0002')).toBeInTheDocument();
    expect(screen.getByText(/Showing/)).toHaveTextContent('Showing 1 of 2 tickets');
  });

  it('combines status, category, urgency, and department filters', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0001');
    await user.click(screen.getByRole('button', { name: 'Resolved' }));
    await user.selectOptions(screen.getByLabelText('Category'), 'waste');
    await user.selectOptions(screen.getByLabelText('Urgency'), 'medium');
    await user.selectOptions(
      screen.getByLabelText('Department'),
      'd2222222-2222-2222-2222-222222222222',
    );

    await waitFor(() =>
      expect(fetchTickets).toHaveBeenLastCalledWith({
        status: 'RESOLVED',
        category: 'waste',
        urgency: 'medium',
        departmentId: 'd2222222-2222-2222-2222-222222222222',
      }),
    );
    expect(screen.queryByText('BG-2026-0001')).not.toBeInTheDocument();
    expect(screen.getByText('BG-2026-0002')).toBeInTheDocument();
  });

  it('shows a filtered empty state when filters match no tickets', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0001');
    await user.click(screen.getByRole('button', { name: 'Closed' }));

    expect(screen.getByText('No matching tickets')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Try adjusting your search, status, category, urgency, or department filters to find tickets.',
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText('BG-2026-0001')).not.toBeInTheDocument();
    expect(screen.queryByText('BG-2026-0002')).not.toBeInTheDocument();
  });

  it('shows a filtered empty state when the server returns no filtered tickets', async () => {
    const user = userEvent.setup();
    vi.mocked(fetchTickets).mockResolvedValueOnce(tickets).mockResolvedValueOnce([]);

    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0001');
    await user.click(screen.getByRole('button', { name: 'Closed' }));

    await waitFor(() => expect(fetchTickets).toHaveBeenCalledTimes(2));
    expect(screen.getByText('No matching tickets')).toBeInTheDocument();
    expect(screen.getByText(/Showing/)).toHaveTextContent('Showing 0 of 2 tickets');
  });

  it('shows an empty state when the dashboard has no tickets', async () => {
    vi.mocked(fetchTickets).mockResolvedValue([]);

    renderWithProviders(<TicketListPage />);

    expect(await screen.findByText('No tickets yet')).toBeInTheDocument();
    expect(
      screen.getByText('Submitted citizen reports will appear here once they are available.'),
    ).toBeInTheDocument();
    const stats = within(screen.getByRole('group', { name: 'Ticket summary' }));
    expect(stats.getByText('Total Tickets').previousElementSibling).toHaveTextContent('0');
    expect(stats.getByText('Open Tickets').previousElementSibling).toHaveTextContent('0');
    expect(stats.getByText('Completed Tickets').previousElementSibling).toHaveTextContent('0');
    expect(stats.getByText('High Urgency').previousElementSibling).toHaveTextContent('0');
  });

  it('shows a failure state when tickets cannot be loaded', async () => {
    vi.mocked(fetchTickets).mockRejectedValue(new Error('Unable to reach backend.'));

    renderWithProviders(<TicketListPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load tickets');
    expect(screen.getByText('Unable to reach backend.')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText('Loading tickets…')).not.toBeInTheDocument());
  });
});

import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TicketListPage } from '@/pages/TicketListPage';
import {
  assignTicketDepartment,
  fetchTicketAggregates,
  fetchTicketsPage,
  updateTicketStatus,
} from '@/services/tickets';
import { renderWithProviders } from '@/test/render';
import type { Ticket } from '@/types/ticket';
import type { TicketAggregates } from '@/types/ticketCollection';

vi.mock('@/services/tickets', async () => {
  const actual = await vi.importActual<typeof import('@/services/tickets')>('@/services/tickets');
  return {
    ...actual,
    fetchTicketsPage: vi.fn(),
    fetchTicketAggregates: vi.fn(),
    updateTicketStatus: vi.fn(),
    assignTicketDepartment: vi.fn(),
    acceptAiCategory: vi.fn(),
    updateTicketCategory: vi.fn(),
  };
});

type FetchPageOptions = Parameters<typeof fetchTicketsPage>[0];

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

const defaultAggregates: TicketAggregates = {
  openCount: 2,
  criticalCount: 0,
  highCount: 1,
  unassignedCount: 0,
  overdueCount: 0,
  approximate: false,
};

function pageFromTickets(items: Ticket[]) {
  return {
    items: [],
    tickets: items,
    nextCursor: null,
    previousCursor: null,
    limit: 25,
    scannedCount: items.length,
    approximateTotal: items.length,
    freshnessHintSeconds: 30,
    fromCache: false,
  };
}

function applyFetchFilters(items: Ticket[], options: FetchPageOptions = {}) {
  const filters = options.filters ?? {};
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
    vi.mocked(fetchTicketsPage).mockImplementation(async (options) =>
      pageFromTickets(applyFetchFilters(tickets, options)),
    );
    vi.mocked(fetchTicketAggregates).mockResolvedValue(defaultAggregates);
  });

  it('shows a loading state while tickets are being fetched', () => {
    vi.mocked(fetchTicketsPage).mockReturnValue(new Promise(() => undefined));

    renderWithProviders(<TicketListPage />);

    expect(screen.getByText('Loading tickets…')).toBeInTheDocument();
  });

  it('renders attention summary and ticket rows after a successful load', async () => {
    renderWithProviders(<TicketListPage />);

    expect(await screen.findByText('BG-2026-0001')).toBeInTheDocument();
    expect(screen.getByText('ROAD01')).toBeInTheDocument();
    expect(screen.getByText('Hamra, Beirut')).toBeInTheDocument();
    expect(screen.getByText('BG-2026-0002')).toBeInTheDocument();
    expect(screen.getByText('Downtown Beirut')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'Work queue' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: 'Citizen reports' })).toBeInTheDocument();
    const stats = within(screen.getByRole('group', { name: 'Ticket summary' }));
    expect(stats.getByText('Critical')).toBeInTheDocument();
    expect(stats.getByText('Unassigned')).toBeInTheDocument();
    expect(stats.getByText('Overdue')).toBeInTheDocument();
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
      expect(fetchTicketsPage).toHaveBeenLastCalledWith(
        expect.objectContaining({
          filters: expect.objectContaining({ status: 'RESOLVED' }),
        }),
      ),
    );
    expect(screen.queryByText('BG-2026-0001')).not.toBeInTheDocument();
    expect(screen.getByText('BG-2026-0002')).toBeInTheDocument();
    expect(screen.getByText(/Showing/)).toHaveTextContent('Showing 1 of 2 tickets');
  });

  it('keeps the dashboard visible while filter results refresh', async () => {
    const user = userEvent.setup();
    let resolveFilteredTickets: (value: ReturnType<typeof pageFromTickets>) => void = () =>
      undefined;
    vi.mocked(fetchTicketsPage)
      .mockResolvedValueOnce(pageFromTickets(tickets))
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

    resolveFilteredTickets(pageFromTickets([tickets[1]]));
    await waitFor(() => expect(screen.queryByText('Updating...')).not.toBeInTheDocument());
  });

  it('filters the rendered ticket list by category', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0001');
    await user.selectOptions(screen.getByLabelText('Category'), 'waste');

    await waitFor(() =>
      expect(fetchTicketsPage).toHaveBeenLastCalledWith(
        expect.objectContaining({
          filters: expect.objectContaining({ category: 'waste' }),
        }),
      ),
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
      expect(fetchTicketsPage).toHaveBeenLastCalledWith(
        expect.objectContaining({
          filters: expect.objectContaining({ urgency: 'high' }),
        }),
      ),
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
      expect(fetchTicketsPage).toHaveBeenLastCalledWith(
        expect.objectContaining({
          filters: expect.objectContaining({
            departmentId: 'd2222222-2222-2222-2222-222222222222',
          }),
        }),
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
      expect(fetchTicketsPage).toHaveBeenLastCalledWith(
        expect.objectContaining({
          filters: {
            status: 'RESOLVED',
            category: 'waste',
            urgency: 'medium',
            departmentId: 'd2222222-2222-2222-2222-222222222222',
            slaState: 'ALL',
          },
        }),
      ),
    );
    expect(screen.queryByText('BG-2026-0001')).not.toBeInTheDocument();
    expect(screen.getByText('BG-2026-0002')).toBeInTheDocument();
  });

  it('requests the overdue SLA queue filter', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0001');
    await user.selectOptions(screen.getByLabelText('SLA'), 'overdue');

    await waitFor(() =>
      expect(fetchTicketsPage).toHaveBeenLastCalledWith(
        expect.objectContaining({
          filters: expect.objectContaining({ slaState: 'overdue' }),
        }),
      ),
    );
  });

  it('shows a filtered empty state when filters match no tickets', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0001');
    await user.click(screen.getByRole('button', { name: 'Closed' }));

    expect(await screen.findByText('No matching tickets')).toBeInTheDocument();
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
    vi.mocked(fetchTicketsPage)
      .mockResolvedValueOnce(pageFromTickets(tickets))
      .mockResolvedValueOnce(pageFromTickets([]));

    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0001');
    await user.click(screen.getByRole('button', { name: 'Closed' }));

    await waitFor(() => expect(fetchTicketsPage).toHaveBeenCalledTimes(2));
    expect(screen.getByText('No matching tickets')).toBeInTheDocument();
    expect(screen.getByText(/Showing/)).toHaveTextContent('Showing 0 of 2 tickets');
  });

  it('shows an empty state when the dashboard has no tickets', async () => {
    vi.mocked(fetchTicketsPage).mockResolvedValue(pageFromTickets([]));
    vi.mocked(fetchTicketAggregates).mockResolvedValue({
      ...defaultAggregates,
      openCount: 0,
      highCount: 0,
    });

    renderWithProviders(<TicketListPage />);

    expect(await screen.findByText('No tickets yet')).toBeInTheDocument();
    expect(
      screen.getByText('Submitted citizen reports will appear here once they are available.'),
    ).toBeInTheDocument();
    const stats = within(screen.getByRole('group', { name: 'Ticket summary' }));
    expect(stats.getByText('Critical').previousElementSibling).toHaveTextContent('0');
    expect(stats.getByText('Unassigned').previousElementSibling).toHaveTextContent('0');
    expect(stats.getByText('Overdue').previousElementSibling).toHaveTextContent('0');
  });

  it('filters the queue to critical urgency from the attention strip', async () => {
    const user = userEvent.setup();
    const criticalTicket: Ticket = {
      ...tickets[0],
      ticketId: 'tkt_critical',
      ticketNumber: 'BG-2026-0009',
      trackingCode: 'CRIT01',
      priority: 'critical',
      status: 'SUBMITTED',
    };
    const closedCritical: Ticket = {
      ...tickets[0],
      ticketId: 'tkt_closed_critical',
      ticketNumber: 'BG-2026-0011',
      trackingCode: 'CLCRIT',
      priority: 'critical',
      status: 'CLOSED',
    };
    vi.mocked(fetchTicketsPage).mockImplementation(async (options) =>
      pageFromTickets(applyFetchFilters([...tickets, criticalTicket, closedCritical], options)),
    );

    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0001');
    await user.click(screen.getByRole('button', { name: /Critical/i }));

    await waitFor(() =>
      expect(fetchTicketsPage).toHaveBeenLastCalledWith(
        expect.objectContaining({
          filters: expect.objectContaining({ urgency: 'critical' }),
        }),
      ),
    );
    expect(await screen.findByText('BG-2026-0009')).toBeInTheDocument();
    expect(screen.queryByText('BG-2026-0011')).not.toBeInTheDocument();
  });

  it('shows a failure state when tickets cannot be loaded', async () => {
    vi.mocked(fetchTicketsPage).mockRejectedValue(new Error('Unable to reach backend.'));

    renderWithProviders(<TicketListPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load tickets');
    expect(screen.getByText('Unable to reach backend.')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText('Loading tickets…')).not.toBeInTheDocument());
  });

  it('removes a ticket from the active status filter after a preview status change', async () => {
    const user = userEvent.setup();
    const submitted: Ticket = {
      ...tickets[0],
      ticketId: 'tkt_submitted',
      ticketNumber: 'BG-2026-0010',
      trackingCode: 'SUBM01',
      status: 'SUBMITTED',
      departmentId: null,
      departmentName: undefined,
    };
    vi.mocked(fetchTicketsPage).mockImplementation(async (options) =>
      pageFromTickets(applyFetchFilters([submitted, ...tickets], options)),
    );
    vi.mocked(updateTicketStatus).mockResolvedValue({
      ...submitted,
      status: 'UNDER_REVIEW',
    });

    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0010');
    await user.click(screen.getByRole('button', { name: 'Submitted' }));
    await waitFor(() =>
      expect(fetchTicketsPage).toHaveBeenLastCalledWith(
        expect.objectContaining({
          filters: expect.objectContaining({ status: 'SUBMITTED' }),
        }),
      ),
    );
    expect(screen.getByText('BG-2026-0010')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Select ticket BG-2026-0010' }));
    const preview = await screen.findByRole('complementary', { name: 'Ticket preview' });
    expect(within(preview).getByRole('heading', { name: 'BG-2026-0010' })).toBeInTheDocument();
    const statusSelect = within(preview).getByRole('combobox', { name: /^Status$/i });
    await user.selectOptions(statusSelect, 'UNDER_REVIEW');
    await user.click(within(preview).getByRole('button', { name: 'Apply status change' }));

    await waitFor(() => expect(updateTicketStatus).toHaveBeenCalled());
    expect(
      screen.queryByRole('button', { name: 'Select ticket BG-2026-0010' }),
    ).not.toBeInTheDocument();
  });

  it('removes a ticket from the Unassigned view after assigning a department in preview', async () => {
    const user = userEvent.setup();
    const unassigned: Ticket = {
      ...tickets[0],
      ticketId: 'tkt_unassigned',
      ticketNumber: 'BG-2026-0011',
      trackingCode: 'UNAS01',
      status: 'SUBMITTED',
      departmentId: null,
      departmentName: undefined,
    };
    vi.mocked(fetchTicketsPage).mockResolvedValue(pageFromTickets([unassigned, ...tickets]));
    vi.mocked(assignTicketDepartment).mockResolvedValue({
      ...unassigned,
      departmentId: 'd1111111-1111-1111-1111-111111111111',
      departmentName: 'Road Maintenance',
    });

    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0011');
    await user.click(screen.getByRole('button', { name: /Unassigned/i }));
    expect(screen.getByRole('button', { name: 'Select ticket BG-2026-0011' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Select ticket BG-2026-0011' }));
    const preview = await screen.findByRole('complementary', { name: 'Ticket preview' });
    expect(within(preview).getByRole('heading', { name: 'BG-2026-0011' })).toBeInTheDocument();
    const departmentSelect = within(preview).getByRole('combobox', { name: /Department/i });
    await user.selectOptions(departmentSelect, 'd1111111-1111-1111-1111-111111111111');
    await user.click(within(preview).getByRole('button', { name: 'Save department' }));

    await waitFor(() => expect(assignTicketDepartment).toHaveBeenCalled());
    expect(
      screen.queryByRole('button', { name: 'Select ticket BG-2026-0011' }),
    ).not.toBeInTheDocument();
  });
});

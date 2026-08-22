import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { resetLocaleForTests, setLocale, t } from '@/i18n';

import { TicketListPage } from '@/pages/TicketListPage';
import { queryStaffAssistant } from '@/services/staffAssistant';
import {
  assignTicketDepartment,
  bulkAssignTicketDepartment,
  fetchTicketAggregates,
  fetchTicketById,
  fetchTicketsPage,
  updateTicketStatus,
} from '@/services/tickets';
import { renderWithProviders } from '@/test/render';
import type { StaffAssistantResponse } from '@/types/staffAssistant';
import type { Ticket } from '@/types/ticket';
import type { TicketAggregates } from '@/types/ticketCollection';

vi.mock('@/services/staffAssistant', () => ({
  queryStaffAssistant: vi.fn(),
}));

vi.mock('@/services/tickets', async () => {
  const actual = await vi.importActual<typeof import('@/services/tickets')>('@/services/tickets');
  return {
    ...actual,
    fetchTicketsPage: vi.fn(),
    fetchTicketAggregates: vi.fn(),
    fetchTicketById: vi.fn(),
    fetchTicketActivity: vi.fn(async () => ({ events: [], nextCursor: null })),
    fetchTicketComments: vi.fn(async () => []),
    fetchImageRedactionReview: vi.fn(async () => null),
    fetchContentSafetyReview: vi.fn(async () => null),
    updateTicketStatus: vi.fn(),
    assignTicketDepartment: vi.fn(),
    acceptAiCategory: vi.fn(),
    updateTicketCategory: vi.fn(),
    reviewTicketCategory: vi.fn(),
    bulkAssignTicketDepartment: vi.fn(),
    bulkAssignTicketWorkforce: vi.fn(),
    fetchAssignmentHistory: vi.fn(async () => ({ ticketId: '', items: [] })),
  };
});

vi.mock('@/services/workOrders', () => ({
  listTicketWorkOrders: vi.fn(async () => ({ items: [], activeWorkOrderId: null })),
  createTicketWorkOrder: vi.fn(),
  assignWorkOrder: vi.fn(),
  startWorkOrder: vi.fn(),
  completeWorkOrder: vi.fn(),
  cancelWorkOrder: vi.fn(),
  uploadWorkOrderEvidence: vi.fn(),
}));

vi.mock('@/services/resolutionFeedback', () => ({
  fetchResolutionFeedback: vi.fn(async () => ({
    ticketId: 'tkt_road',
    trackingCode: 'ROAD01',
    ticketStatus: 'IN_PROGRESS',
    status: null,
    note: null,
    submittedAt: null,
    reviewStatus: null,
    reviewedAt: null,
    reviewedBy: null,
    reviewAction: null,
    needsReview: false,
  })),
  reviewResolutionFeedback: vi.fn(),
}));

vi.mock('@/services/workforce', () => ({
  listWorkers: vi.fn(async () => []),
  listTeams: vi.fn(async () => []),
  fetchWorkload: vi.fn(),
}));

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
    if (filters.slaState && filters.slaState !== 'ALL' && ticket.sla?.state !== filters.slaState) {
      return false;
    }
    if (filters.assignmentState === 'unassigned' && ticket.departmentId) {
      return false;
    }
    if (filters.assignmentState === 'assigned' && !ticket.departmentId) {
      return false;
    }
    if (filters.openOnly) {
      const open = new Set(['SUBMITTED', 'UNDER_REVIEW', 'ASSIGNED', 'IN_PROGRESS']);
      if (!open.has(ticket.status)) {
        return false;
      }
    }
    if (
      filters.ticketIds &&
      filters.ticketIds.length > 0 &&
      !filters.ticketIds.includes(ticket.ticketId)
    ) {
      return false;
    }
    const query = filters.q?.trim().toLowerCase();
    if (query) {
      const haystack = [
        ticket.ticketId,
        ticket.ticketNumber,
        ticket.trackingCode,
        ticket.description,
        ticket.location.addressText,
      ]
        .join(' ')
        .toLowerCase();
      if (!haystack.includes(query)) {
        return false;
      }
    }
    return true;
  });
}

describe('TicketListPage', () => {
  beforeEach(() => {
    resetLocaleForTests();
    vi.clearAllMocks();
    vi.mocked(fetchTicketsPage).mockImplementation(async (options) =>
      pageFromTickets(applyFetchFilters(tickets, options)),
    );
    vi.mocked(fetchTicketAggregates).mockResolvedValue(defaultAggregates);
    vi.mocked(fetchTicketById).mockImplementation(async (ticketId) => {
      return tickets.find((ticket) => ticket.ticketId === ticketId) ?? null;
    });
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

  it('localizes the ticket list chrome for Arabic and French', async () => {
    renderWithProviders(<TicketListPage />);
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Work queue' }),
    ).toBeInTheDocument();

    await act(async () => {
      setLocale('ar');
    });
    expect(
      screen.getByRole('heading', { level: 1, name: t('tickets.queueTitle') }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(t('filters.category'))).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 2, name: t('queue.needsAttention') }),
    ).toBeInTheDocument();

    await act(async () => {
      setLocale('fr');
    });
    expect(
      screen.getByRole('heading', { level: 1, name: t('tickets.queueTitle') }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 2, name: t('tickets.citizenReports') }),
    ).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent(
      t('tickets.opsCounts', {
        queued: 0,
        assigned: 0,
        inProgress: 0,
        dueSoon: 0,
        workforceUnassigned: 0,
        completed: 0,
        cancelled: 0,
      }),
    );
  });

  it('lets staff select tickets, preview a bulk assignment, then commit it', async () => {
    const user = userEvent.setup();
    vi.mocked(bulkAssignTicketDepartment).mockResolvedValue({
      dryRun: true,
      attempted: 1,
      succeeded: 1,
      failed: 0,
      items: [{ ticketId: 'tkt_road', ok: true, code: 'PREVIEW' }],
    });

    renderWithProviders(<TicketListPage />);
    await screen.findByRole('checkbox', { name: 'Add BG-2026-0001 to bulk assignment' });

    await user.click(screen.getByRole('checkbox', { name: 'Add BG-2026-0001 to bulk assignment' }));
    expect(screen.getByLabelText('Bulk assignment')).toBeInTheDocument();

    const { DEPARTMENT_OPTIONS } = await import('@/utils/departments');
    const bulk = within(screen.getByLabelText('Bulk assignment'));
    await user.selectOptions(
      bulk.getByRole('combobox', { name: 'Department' }),
      DEPARTMENT_OPTIONS[0]!.departmentId,
    );
    await user.click(bulk.getByRole('button', { name: 'Preview' }));
    expect(await bulk.findByText(/1 succeeded/)).toBeInTheDocument();

    vi.mocked(bulkAssignTicketDepartment).mockResolvedValue({
      dryRun: false,
      attempted: 1,
      succeeded: 1,
      failed: 0,
      items: [{ ticketId: 'tkt_road', ok: true }],
    });
    const pageCallsBeforeCommit = vi.mocked(fetchTicketsPage).mock.calls.length;
    const aggregateCallsBeforeCommit = vi.mocked(fetchTicketAggregates).mock.calls.length;
    await user.click(bulk.getByRole('button', { name: 'Commit' }));

    await waitFor(() => {
      expect(vi.mocked(fetchTicketsPage).mock.calls.length).toBeGreaterThan(pageCallsBeforeCommit);
      expect(vi.mocked(fetchTicketAggregates).mock.calls.length).toBeGreaterThan(
        aggregateCallsBeforeCommit,
      );
    });
    expect(screen.queryByLabelText('Bulk assignment')).not.toBeInTheDocument();
    expect(
      await screen.findByRole('checkbox', { name: 'Add BG-2026-0001 to bulk assignment' }),
    ).not.toBeChecked();
  });

  it('keeps per-ticket results visible when a bulk commit only partly succeeds', async () => {
    const user = userEvent.setup();
    vi.mocked(bulkAssignTicketDepartment).mockResolvedValue({
      dryRun: true,
      attempted: 2,
      succeeded: 1,
      failed: 1,
      items: [
        { ticketId: 'tkt_road', ok: true, code: 'PREVIEW' },
        { ticketId: 'tkt_waste', ok: false, code: 'FORBIDDEN', message: 'Out of scope.' },
      ],
    });

    renderWithProviders(<TicketListPage />);
    await screen.findByRole('checkbox', { name: 'Add BG-2026-0001 to bulk assignment' });
    await user.click(screen.getByRole('checkbox', { name: 'Add BG-2026-0001 to bulk assignment' }));
    await user.click(screen.getByRole('checkbox', { name: 'Add BG-2026-0002 to bulk assignment' }));

    const { DEPARTMENT_OPTIONS } = await import('@/utils/departments');
    const bulk = within(screen.getByLabelText('Bulk assignment'));
    await user.selectOptions(
      bulk.getByRole('combobox', { name: 'Department' }),
      DEPARTMENT_OPTIONS[0]!.departmentId,
    );
    await user.click(bulk.getByRole('button', { name: 'Preview' }));
    expect(await bulk.findByText(/1 succeeded/)).toBeInTheDocument();

    vi.mocked(bulkAssignTicketDepartment).mockResolvedValue({
      dryRun: false,
      attempted: 2,
      succeeded: 1,
      failed: 1,
      items: [
        { ticketId: 'tkt_road', ok: true },
        { ticketId: 'tkt_waste', ok: false, code: 'FORBIDDEN', message: 'Out of scope.' },
      ],
    });
    const pageCallsBeforeCommit = vi.mocked(fetchTicketsPage).mock.calls.length;
    await user.click(bulk.getByRole('button', { name: 'Commit' }));

    await waitFor(() => {
      expect(vi.mocked(fetchTicketsPage).mock.calls.length).toBeGreaterThan(pageCallsBeforeCommit);
    });
    const committed = within(screen.getByLabelText('Bulk assignment'));
    expect(committed.getByText(/Committed/)).toBeInTheDocument();
    expect(committed.getByText(/Out of scope/)).toBeInTheDocument();
    expect(
      screen.getByRole('checkbox', { name: 'Add BG-2026-0001 to bulk assignment' }),
    ).not.toBeChecked();
    expect(
      screen.getByRole('checkbox', { name: 'Add BG-2026-0002 to bulk assignment' }),
    ).toBeChecked();
  });

  const assistantListAnswer: StaffAssistantResponse = {
    intent: 'high_priority_summary',
    asOf: '2026-08-15T12:00:00Z',
    message: '2 accessible high-priority or critical ticket(s) in the open operational queue.',
    count: 2,
    categories: { road_damage: 2 },
    statuses: { IN_PROGRESS: 2 },
    departments: {},
    areas: {},
    areaClusters: [
      {
        cellId: 'c1',
        south: 33.8,
        west: 35.4,
        north: 33.9,
        east: 35.5,
        label: 'Hamra',
        ticketCount: 1,
        distinctReportCount: 1,
        duplicateGroupCount: 0,
        separateReportCount: 1,
        categories: { road_damage: 1 },
        ticketIds: ['tkt_road'],
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

  it('applies assistant list filters when already on the ticket list route', async () => {
    vi.mocked(queryStaffAssistant).mockResolvedValue(assistantListAnswer);
    const user = userEvent.setup();
    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0001');
    await user.click(screen.getByRole('button', { name: 'Assistant' }));
    await user.click(screen.getByRole('button', { name: 'Show high-priority tickets' }));
    const listActions = await screen.findAllByRole('button', { name: 'View matching tickets' });
    await user.click(listActions[0]);

    await waitFor(() =>
      expect(fetchTicketsPage).toHaveBeenCalledWith(
        expect.objectContaining({
          filters: expect.objectContaining({
            urgency: 'high,critical',
            openOnly: true,
          }),
        }),
      ),
    );
    expect(window.location.pathname).toBe('/');
    expect(window.location.search).toContain('urgency=high%2Ccritical');
    expect(window.location.search).toContain('openOnly=true');
  });

  it('applies assistant cluster ticket ids when already on the ticket list route', async () => {
    vi.mocked(queryStaffAssistant).mockResolvedValue(assistantListAnswer);
    const user = userEvent.setup();
    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0001');
    await user.click(screen.getByRole('button', { name: 'Assistant' }));
    await user.click(screen.getByRole('button', { name: 'Show high-priority tickets' }));
    const clusterActions = await screen.findAllByRole('button', { name: 'View matching tickets' });
    await user.click(clusterActions[1]);

    await waitFor(() =>
      expect(fetchTicketsPage).toHaveBeenCalledWith(
        expect.objectContaining({
          filters: expect.objectContaining({
            openOnly: true,
            ticketIds: ['tkt_road'],
          }),
        }),
      ),
    );
    expect(window.location.search).toContain('ticketIds=tkt_road');
    expect(window.location.search).toContain('openOnly=true');
  });

  it('applies safe assistant filters from the URL and keeps them after interaction', async () => {
    renderWithProviders(<TicketListPage />, {
      route: '/?urgency=high,critical&openOnly=true&ticketIds=tkt_missing',
    });

    await waitFor(() =>
      expect(fetchTicketsPage).toHaveBeenCalledWith(
        expect.objectContaining({
          filters: expect.objectContaining({
            urgency: 'high,critical',
            openOnly: true,
            ticketIds: ['tkt_missing'],
          }),
        }),
      ),
    );
    expect(await screen.findByText('These tickets are no longer available')).toBeInTheDocument();
    expect(window.location.search).toContain('openOnly=true');
    expect(window.location.search).not.toContain('description');
  });

  it('filters the rendered ticket list by search text', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0001');
    await user.type(screen.getByLabelText('Search tickets'), 'WASTE2');

    await waitFor(() =>
      expect(fetchTicketsPage).toHaveBeenLastCalledWith(
        expect.objectContaining({
          filters: expect.objectContaining({ q: 'WASTE2' }),
        }),
      ),
    );
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
          filters: expect.objectContaining({
            status: 'RESOLVED',
            category: 'waste',
            urgency: 'medium',
            departmentId: 'd2222222-2222-2222-2222-222222222222',
          }),
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

  it('shows a failure state when tickets cannot be loaded and retries', async () => {
    const user = userEvent.setup();
    vi.mocked(fetchTicketsPage)
      .mockRejectedValueOnce(new Error('Unable to reach backend.'))
      .mockImplementation(async (options) =>
        pageFromTickets(applyFetchFilters(tickets, options)),
      );

    renderWithProviders(<TicketListPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load tickets');
    expect(screen.getByText('Unable to reach backend.')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText('Loading tickets…')).not.toBeInTheDocument());

    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('BG-2026-0001')).toBeInTheDocument();
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
    vi.mocked(fetchTicketById).mockResolvedValue(submitted);
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
    expect(
      await within(preview).findByRole('heading', { name: 'BG-2026-0010' }),
    ).toBeInTheDocument();
    const statusSelect = await within(preview).findByRole('combobox', { name: /^Status$/i });
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
    vi.mocked(fetchTicketById).mockResolvedValue(unassigned);
    vi.mocked(assignTicketDepartment).mockResolvedValue({
      ...unassigned,
      departmentId: 'd1111111-1111-1111-1111-111111111111',
      departmentName: 'Road Maintenance',
    });

    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0011');
    await user.click(screen.getByRole('button', { name: /Unassigned/i }));
    await waitFor(() =>
      expect(fetchTicketsPage).toHaveBeenLastCalledWith(
        expect.objectContaining({
          filters: expect.objectContaining({ assignmentState: 'unassigned' }),
        }),
      ),
    );
    expect(screen.getByRole('button', { name: 'Select ticket BG-2026-0011' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Select ticket BG-2026-0011' }));
    const preview = await screen.findByRole('complementary', { name: 'Ticket preview' });
    expect(
      await within(preview).findByRole('heading', { name: 'BG-2026-0011' }),
    ).toBeInTheDocument();
    const departmentSelect = await within(preview).findByRole('combobox', {
      name: /Department/i,
    });
    await user.selectOptions(departmentSelect, 'd1111111-1111-1111-1111-111111111111');
    await user.click(within(preview).getByRole('button', { name: 'Save department' }));

    await waitFor(() => expect(assignTicketDepartment).toHaveBeenCalled());
    expect(
      screen.queryByRole('button', { name: 'Select ticket BG-2026-0011' }),
    ).not.toBeInTheDocument();
  });

  it('keeps the ticket list full width until a ticket is selected', async () => {
    renderWithProviders(<TicketListPage />);

    expect(await screen.findByText('BG-2026-0001')).toBeInTheDocument();
    expect(screen.queryByRole('complementary', { name: 'Ticket preview' })).not.toBeInTheDocument();
    expect(document.querySelector('.helpdesk-desk--preview-open')).not.toBeInTheDocument();
  });

  it('opens a sliding preview drawer when a ticket is selected', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0001');
    await user.click(screen.getByRole('button', { name: 'Select ticket BG-2026-0001' }));

    const preview = await screen.findByRole('complementary', { name: 'Ticket preview' });
    expect(
      await within(preview).findByRole('heading', { name: 'BG-2026-0001' }),
    ).toBeInTheDocument();
    expect(within(preview).getAllByRole('link', { name: 'Open' })[0]).toHaveAttribute(
      'href',
      '/tickets/tkt_road',
    );
    expect(document.querySelector('.helpdesk-desk--preview-open')).toBeInTheDocument();
    await waitFor(() => expect(fetchTicketById).toHaveBeenCalledWith('tkt_road'));
  });

  it('closes the preview drawer and restores the full-width list', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0001');
    await user.click(screen.getByRole('button', { name: 'Select ticket BG-2026-0001' }));
    const preview = await screen.findByRole('complementary', { name: 'Ticket preview' });
    await user.click(within(preview).getByRole('button', { name: 'Close preview' }));

    expect(screen.queryByRole('complementary', { name: 'Ticket preview' })).not.toBeInTheDocument();
    expect(document.querySelector('.helpdesk-desk--preview-open')).not.toBeInTheDocument();
  });

  it('opens the full ticket workspace from the preview Open button', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TicketListPage />);

    await screen.findByText('BG-2026-0001');
    await user.click(screen.getByRole('button', { name: 'Select ticket BG-2026-0001' }));
    const preview = await screen.findByRole('complementary', { name: 'Ticket preview' });
    await within(preview).findByRole('heading', { name: 'BG-2026-0001' });
    await user.click(within(preview).getAllByRole('link', { name: 'Open' })[0]);

    expect(window.location.pathname).toBe('/tickets/tkt_road');
  });

  it('keeps preview mutations disabled until the full ticket loads', async () => {
    const user = userEvent.setup();
    let resolvePreview: (ticket: Ticket) => void = () => undefined;
    vi.mocked(fetchTicketById).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolvePreview = resolve;
        }),
    );

    renderWithProviders(<TicketListPage />);
    await screen.findByText('BG-2026-0001');
    await user.click(screen.getByRole('button', { name: 'Select ticket BG-2026-0001' }));

    const preview = await screen.findByRole('complementary', { name: 'Ticket preview' });
    expect(within(preview).getByText('Loading…')).toBeInTheDocument();
    expect(within(preview).queryByRole('button', { name: 'Publish' })).not.toBeInTheDocument();
    expect(
      within(preview).queryByRole('button', { name: 'Save final category' }),
    ).not.toBeInTheDocument();

    resolvePreview(tickets[0]);
    expect(
      await within(preview).findByRole('heading', { name: 'BG-2026-0001' }),
    ).toBeInTheDocument();
    expect(within(preview).getByRole('button', { name: 'Publish' })).toBeInTheDocument();
  });

  it('does not keep list-projection Publish or Save controls after fetchTicketById fails', async () => {
    const user = userEvent.setup();
    const listProjection: Ticket = {
      ...tickets[0],
      imageObjectKey: 'unavailable',
      imageUrl: undefined,
      ai: undefined,
      public: undefined,
    };
    vi.mocked(fetchTicketsPage).mockResolvedValue(pageFromTickets([listProjection]));
    vi.mocked(fetchTicketById)
      .mockRejectedValueOnce(new Error('Unable to reach backend.'))
      .mockResolvedValueOnce(tickets[0]);

    renderWithProviders(<TicketListPage />);
    await screen.findByText('BG-2026-0001');
    await user.click(screen.getByRole('button', { name: 'Select ticket BG-2026-0001' }));

    const preview = await screen.findByRole('complementary', { name: 'Ticket preview' });
    expect(await within(preview).findByRole('alert')).toHaveTextContent('Unable to reach backend.');
    expect(within(preview).queryByRole('button', { name: 'Publish' })).not.toBeInTheDocument();
    expect(
      within(preview).queryByRole('button', { name: 'Save final category' }),
    ).not.toBeInTheDocument();
    expect(
      within(preview).queryByRole('button', { name: 'Save department' }),
    ).not.toBeInTheDocument();
    expect(within(preview).queryByRole('img', { name: /BG-2026-0001/i })).not.toBeInTheDocument();

    await user.click(within(preview).getByRole('button', { name: 'Retry' }));
    expect(
      await within(preview).findByRole('heading', { name: 'BG-2026-0001' }),
    ).toBeInTheDocument();
    expect(within(preview).getByRole('button', { name: 'Publish' })).toBeInTheDocument();
    expect(fetchTicketById).toHaveBeenCalledTimes(2);
  });
});

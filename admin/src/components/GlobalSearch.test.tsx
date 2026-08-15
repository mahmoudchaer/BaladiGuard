import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { GlobalSearch } from '@/components/GlobalSearch';
import { searchStaffRecords } from '@/services/staffSearch';
import { renderWithProviders } from '@/test/render';
import type { StaffSearchResponse } from '@/types/staffSearch';

vi.mock('@/services/staffSearch', () => ({
  searchStaffRecords: vi.fn(),
}));

const emptyResults: StaffSearchResponse = {
  asOf: '2026-08-15T12:00:00Z',
  query: 'zz',
  tickets: [],
  workers: [],
  teams: [],
  workOrders: [],
  ticketsTruncated: false,
  workersTruncated: false,
  teamsTruncated: false,
  workOrdersTruncated: false,
  scanTruncated: false,
  workforceScanTruncated: false,
  workOrderScanTruncated: false,
  partialFailures: [],
  limits: {},
};

const grouped: StaffSearchResponse = {
  ...emptyResults,
  query: 'BG',
  tickets: [
    {
      resultType: 'ticket',
      ticketId: 'tkt_1',
      ticketNumber: 'BG-2026-0001',
      trackingCode: 'AB23CD',
      status: 'IN_PROGRESS',
      category: 'road_damage',
      publicLocationLabel: 'Hamra gate',
    },
  ],
  workers: [
    {
      resultType: 'worker',
      workerId: 'wrk_1',
      displayName: 'Road crew',
      departmentIds: [],
      active: true,
    },
  ],
};

describe('GlobalSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('groups results and navigates without putting the query in the URL', async () => {
    vi.mocked(searchStaffRecords).mockResolvedValue(grouped);
    const user = userEvent.setup();
    renderWithProviders(<GlobalSearch />);

    await user.type(screen.getByLabelText('Search tickets, workers, teams, and work orders'), 'BG');
    expect(await screen.findByText('Tickets')).toBeInTheDocument();
    expect(screen.getByText('Workers')).toBeInTheDocument();

    await user.click(screen.getByRole('option', { name: /BG-2026-0001/i }));
    expect(window.location.pathname).toBe('/tickets/tkt_1');
    expect(window.location.search).not.toContain('BG');
  });

  it('shows empty and error states', async () => {
    vi.mocked(searchStaffRecords)
      .mockRejectedValueOnce(new Error('Search unavailable.'))
      .mockResolvedValueOnce(emptyResults);
    const user = userEvent.setup();
    renderWithProviders(<GlobalSearch />);
    const input = screen.getByLabelText('Search tickets, workers, teams, and work orders');

    await user.type(input, 'no');
    expect(await screen.findByRole('alert')).toHaveTextContent('Search unavailable.');

    await user.clear(input);
    await user.type(input, 'zz');
    expect(await screen.findByText('No matching operational records.')).toBeInTheDocument();
  });

  it('does not search one-character queries', async () => {
    const user = userEvent.setup();
    renderWithProviders(<GlobalSearch />);
    await user.type(screen.getByLabelText('Search tickets, workers, teams, and work orders'), 'a');
    await waitFor(() => {
      expect(searchStaffRecords).not.toHaveBeenCalled();
    });
  });
});

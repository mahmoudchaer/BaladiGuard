import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { BulkTicketAssignmentBar } from '@/components/BulkTicketAssignmentBar';
import { bulkAssignTicketDepartment } from '@/services/tickets';
import { renderWithProviders } from '@/test/render';
import { DEPARTMENT_OPTIONS } from '@/utils/departments';

vi.mock('@/services/tickets', () => ({
  bulkAssignTicketDepartment: vi.fn(),
  bulkAssignTicketWorkforce: vi.fn(),
}));

vi.mock('@/services/workforce', () => ({
  listWorkers: vi.fn(async () => []),
  listTeams: vi.fn(async () => []),
}));

describe('BulkTicketAssignmentBar', () => {
  beforeEach(() => {
    vi.mocked(bulkAssignTicketDepartment).mockReset();
  });

  it('previews then commits a department assignment and shows per-item results', async () => {
    const user = userEvent.setup();
    vi.mocked(bulkAssignTicketDepartment)
      .mockResolvedValueOnce({
        dryRun: true,
        attempted: 2,
        succeeded: 1,
        failed: 1,
        items: [
          { ticketId: 'tkt_road', ok: true, code: 'PREVIEW' },
          { ticketId: 'tkt_waste', ok: false, code: 'FORBIDDEN', message: 'Out of scope.' },
        ],
      })
      .mockResolvedValueOnce({
        dryRun: false,
        attempted: 2,
        succeeded: 1,
        failed: 1,
        items: [
          { ticketId: 'tkt_road', ok: true },
          { ticketId: 'tkt_waste', ok: false, code: 'FORBIDDEN', message: 'Out of scope.' },
        ],
      });

    renderWithProviders(
      <BulkTicketAssignmentBar
        selectedTicketIds={['tkt_road', 'tkt_waste']}
        ticketNumbers={{ tkt_road: 'BG-2026-0001', tkt_waste: 'BG-2026-0002' }}
        onClear={() => undefined}
      />,
    );

    expect(screen.getByLabelText('Bulk assignment')).toBeInTheDocument();
    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Department' }),
      DEPARTMENT_OPTIONS[0]!.departmentId,
    );
    await user.click(screen.getByRole('button', { name: 'Preview' }));

    await waitFor(() => {
      expect(bulkAssignTicketDepartment).toHaveBeenCalledWith({
        ticketIds: ['tkt_road', 'tkt_waste'],
        departmentId: DEPARTMENT_OPTIONS[0]!.departmentId,
        dryRun: true,
      });
    });
    expect(await screen.findByRole('status')).toHaveTextContent(/1 succeeded/);
    expect(screen.getByText(/Out of scope/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Commit' }));
    await waitFor(() => {
      expect(bulkAssignTicketDepartment).toHaveBeenLastCalledWith({
        ticketIds: ['tkt_road', 'tkt_waste'],
        departmentId: DEPARTMENT_OPTIONS[0]!.departmentId,
        dryRun: false,
      });
    });
    expect(await screen.findByRole('status')).toHaveTextContent(/Committed/);
  });
});

import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/render';
import { WorkforcePage } from '@/pages/WorkforcePage';
import { fetchWorkload, listTeams, listWorkers } from '@/services/workforce';

vi.mock('@/services/workforce', () => ({
  listWorkers: vi.fn(),
  listTeams: vi.fn(),
  fetchWorkload: vi.fn(),
  createWorker: vi.fn(),
  createTeam: vi.fn(),
  setWorkerActive: vi.fn(),
  setTeamActive: vi.fn(),
}));

function installLocalStorage() {
  const store = new Map<string, string>();
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => {
        store.set(key, value);
      },
      removeItem: (key: string) => {
        store.delete(key);
      },
      clear: () => store.clear(),
    },
  });
}

describe('WorkforcePage', () => {
  beforeEach(() => {
    installLocalStorage();
    window.localStorage.setItem(
      'baladiguard.staffSession',
      JSON.stringify({
        username: 'admin',
        name: 'Demo Administrator',
        staffId: 'staff_admin_001',
        role: 'administrator',
        municipalityId: null,
        departmentIds: null,
        signedInAt: '2026-08-14T08:00:00Z',
        accessToken: 'test-admin-token',
      }),
    );
    vi.mocked(listWorkers).mockResolvedValue([
      {
        workerId: 'wrk_1',
        municipalityId: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        displayName: 'Karim Roads',
        departmentIds: ['d1111111-1111-1111-1111-111111111111'],
        teamIds: [],
        active: true,
        createdAt: '2026-08-14T08:00:00Z',
        updatedAt: '2026-08-14T08:00:00Z',
      },
    ]);
    vi.mocked(listTeams).mockResolvedValue([]);
    vi.mocked(fetchWorkload).mockResolvedValue({
      municipalityId: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
      unassigned: { queued: 1, assigned: 0, inProgress: 0, dueSoon: 0, overdue: 0 },
      unassignedTickets: [
        {
          ticketId: 'tkt_open',
          ticketNumber: 'BG-2026-0009',
          status: 'SUBMITTED',
          departmentId: 'd1111111-1111-1111-1111-111111111111',
          slaState: 'on_track',
        },
      ],
      workers: [
        {
          id: 'wrk_1',
          kind: 'worker',
          displayName: 'Karim Roads',
          departmentIds: ['d1111111-1111-1111-1111-111111111111'],
          active: true,
          counts: { queued: 0, assigned: 1, inProgress: 0, dueSoon: 0, overdue: 0 },
          tickets: [
            {
              ticketId: 'tkt_assigned',
              ticketNumber: 'BG-2026-0010',
              status: 'ASSIGNED',
              slaState: 'due_soon',
            },
          ],
        },
      ],
      teams: [],
    });
  });

  it('shows workload comparison and links to tickets', async () => {
    renderWithProviders(<WorkforcePage />);
    expect(await screen.findByText('Unassigned')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'BG-2026-0009' })).toHaveAttribute(
      'href',
      '/tickets/tkt_open',
    );
    expect(screen.getByText('Karim Roads')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'BG-2026-0010' })).toHaveAttribute(
      'href',
      '/tickets/tkt_assigned',
    );
  });

  it('lets administrators manage the directory', async () => {
    const user = userEvent.setup();
    renderWithProviders(<WorkforcePage />);
    await user.click(await screen.findByRole('tab', { name: 'Directory' }));
    expect(await screen.findByRole('button', { name: 'Add worker' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Deactivate' })).toBeInTheDocument();
    await waitFor(() => {
      expect(listWorkers).toHaveBeenCalled();
    });
  });
});

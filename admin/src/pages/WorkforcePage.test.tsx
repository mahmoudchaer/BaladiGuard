import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { setLocale, t } from '@/i18n';
import { renderWithProviders } from '@/test/render';
import { WorkforcePage } from '@/pages/WorkforcePage';
import {
  fetchWorkload,
  listTeams,
  listWorkers,
  updateTeam,
  updateWorker,
} from '@/services/workforce';

vi.mock('@/services/workforce', () => ({
  listWorkers: vi.fn(),
  listTeams: vi.fn(),
  fetchWorkload: vi.fn(),
  createWorker: vi.fn(),
  createTeam: vi.fn(),
  updateWorker: vi.fn(),
  updateTeam: vi.fn(),
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
    vi.mocked(listTeams).mockResolvedValue([
      {
        teamId: 'team_1',
        municipalityId: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        displayName: 'Night roads',
        departmentIds: ['d1111111-1111-1111-1111-111111111111'],
        workerIds: [],
        active: true,
        createdAt: '2026-08-14T08:00:00Z',
        updatedAt: '2026-08-14T08:00:00Z',
      },
    ]);
    vi.mocked(updateWorker).mockImplementation(async (_id, input) => ({
      workerId: 'wrk_1',
      municipalityId: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
      displayName: input.displayName ?? 'Karim Roads',
      departmentIds: input.departmentIds ?? ['d1111111-1111-1111-1111-111111111111'],
      teamIds: [],
      active: true,
      createdAt: '2026-08-14T08:00:00Z',
      updatedAt: '2026-08-14T09:00:00Z',
    }));
    vi.mocked(updateTeam).mockImplementation(async (_id, input) => ({
      teamId: 'team_1',
      municipalityId: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
      displayName: input.displayName ?? 'Night roads',
      departmentIds: input.departmentIds ?? ['d1111111-1111-1111-1111-111111111111'],
      workerIds: input.workerIds ?? [],
      active: true,
      createdAt: '2026-08-14T08:00:00Z',
      updatedAt: '2026-08-14T09:00:00Z',
    }));
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

  it('localizes workforce title, directory, and add worker for Arabic and French', async () => {
    const user = userEvent.setup();
    renderWithProviders(<WorkforcePage />);
    expect(await screen.findByText('Unassigned')).toBeInTheDocument();

    await act(async () => {
      setLocale('ar');
    });
    expect(screen.getByRole('heading', { name: t('workforce.title') })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: t('workforce.directory') })).toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: t('workforce.directory') }));
    expect(screen.getByRole('button', { name: t('workforce.addWorker') })).toBeInTheDocument();

    await act(async () => {
      setLocale('fr');
    });
    expect(screen.getByRole('heading', { name: t('workforce.title') })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: t('workforce.directory') })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: t('workforce.addWorker') })).toBeInTheDocument();
  });

  it('lets administrators manage the directory', async () => {
    const user = userEvent.setup();
    renderWithProviders(<WorkforcePage />);
    await user.click(await screen.findByRole('tab', { name: 'Directory' }));
    expect(await screen.findByRole('button', { name: 'Add worker' })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Deactivate' }).length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(listWorkers).toHaveBeenCalled();
    });
  });

  it('saves worker name and departments', async () => {
    const user = userEvent.setup();
    renderWithProviders(<WorkforcePage />);
    await user.click(await screen.findByRole('tab', { name: 'Directory' }));
    const editButtons = await screen.findAllByRole('button', { name: 'Edit' });
    await user.click(editButtons[0]);
    const nameInput = await screen.findByLabelText('Edit worker name');
    await user.clear(nameInput);
    await user.type(nameInput, 'Karim Roads (lead)');
    await user.click(screen.getByRole('button', { name: 'Save worker' }));
    await waitFor(() => {
      expect(updateWorker).toHaveBeenCalledWith('wrk_1', {
        displayName: 'Karim Roads (lead)',
        departmentIds: ['d1111111-1111-1111-1111-111111111111'],
      });
    });
  });

  it('saves team membership', async () => {
    const user = userEvent.setup();
    renderWithProviders(<WorkforcePage />);
    await user.click(await screen.findByRole('tab', { name: 'Directory' }));
    const editButtons = await screen.findAllByRole('button', { name: 'Edit' });
    await user.click(editButtons[1]);
    await user.click(await screen.findByRole('checkbox', { name: 'Karim Roads' }));
    await user.click(screen.getByRole('button', { name: 'Save team' }));
    await waitFor(() => {
      expect(updateTeam).toHaveBeenCalledWith(
        'team_1',
        expect.objectContaining({
          workerIds: ['wrk_1'],
        }),
      );
    });
  });
});

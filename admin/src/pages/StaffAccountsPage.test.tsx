import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { StaffAccountsPage } from '@/pages/StaffAccountsPage';
import { renderWithProviders } from '@/test/render';
import {
  createStaffAccount,
  listStaffAccounts,
  setStaffAccountActive,
  updateStaffAccount,
} from '@/services/staffAccounts';
import type { StaffAccount } from '@/types/staffAccount';

vi.mock('@/services/staffAccounts', () => ({
  createStaffAccount: vi.fn(),
  listStaffAccounts: vi.fn(),
  listStaffDepartments: vi.fn(async () => []),
  setStaffAccountActive: vi.fn(),
  updateStaffAccount: vi.fn(),
}));
vi.mock('@/components/GlobalSearch', () => ({ GlobalSearch: () => null }));
vi.mock('@/components/StaffAssistantPanel', () => ({ StaffAssistantPanel: () => null }));

const BEIRUT = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';
const ROADS = 'd1111111-1111-1111-1111-111111111111';
const account: StaffAccount = {
  staffId: 'staff_muni_001',
  username: 'operator',
  name: 'Road Operator',
  email: 'operator@example.test',
  role: 'municipal_staff',
  municipalityId: BEIRUT,
  departmentIds: [ROADS],
  active: true,
  createdAt: '2026-08-18T00:00:00Z',
  updatedAt: '2026-08-18T00:00:00Z',
};

function installAdminSession() {
  window.localStorage.setItem(
    'baladiguard.staffSession',
    JSON.stringify({
      username: 'admin',
      name: 'Admin',
      staffId: 'staff_admin_001',
      role: 'administrator',
      municipalityId: BEIRUT,
      departmentIds: null,
      signedInAt: '2026-08-18T00:00:00Z',
      accessToken: 'token',
    }),
  );
}

describe('StaffAccountsPage', () => {
  beforeEach(() => {
    window.localStorage.clear();
    installAdminSession();
    vi.clearAllMocks();
    vi.mocked(listStaffAccounts).mockResolvedValue([account]);
    vi.mocked(createStaffAccount).mockImplementation(async (input) => ({
      ...account,
      staffId: 'staff_new',
      username: input.username,
      name: input.name,
      email: input.email,
      role: input.role,
      municipalityId: input.municipalityId,
      departmentIds: input.departmentIds,
    }));
    vi.mocked(updateStaffAccount).mockImplementation(async (_id, input) => ({
      ...account,
      ...input,
    }));
    vi.mocked(setStaffAccountActive).mockImplementation(async (_id, active) => ({
      ...account,
      active,
    }));
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  it('lists safe account fields and retries a failed load', async () => {
    vi.mocked(listStaffAccounts).mockRejectedValueOnce(new Error('Network unavailable'));
    const user = userEvent.setup();
    renderWithProviders(<StaffAccountsPage />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Network unavailable');
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('Road Operator')).toBeInTheDocument();
    expect(screen.getByText('Initial passwords are write-only.')).toBeInTheDocument();
  });

  it('creates municipal staff from the catalog and clears the write-only password', async () => {
    const user = userEvent.setup();
    renderWithProviders(<StaffAccountsPage />);
    await screen.findByText('Road Operator');
    await user.type(screen.getByLabelText('Full name'), 'New Operator');
    await user.type(screen.getByLabelText('Username'), 'new.operator');
    await user.type(screen.getByLabelText('Email'), 'new@example.test');
    const password = screen.getByLabelText('Initial password');
    await user.type(password, 'secret-pass');
    await user.click(screen.getByLabelText('Road Maintenance'));
    await user.click(screen.getByRole('button', { name: 'Create account' }));
    await waitFor(() =>
      expect(createStaffAccount).toHaveBeenCalledWith(
        expect.objectContaining({
          role: 'municipal_staff',
          municipalityId: BEIRUT,
          departmentIds: [ROADS],
          password: 'secret-pass',
        }),
      ),
    );
    expect(password).toHaveValue('');
  });

  it('does not offer administrator creation from the municipality desk', async () => {
    renderWithProviders(<StaffAccountsPage />);
    await screen.findByText('Road Operator');
    const roleSelect = screen.getByLabelText('Role');
    expect(roleSelect).toHaveValue('municipal_staff');
    expect(roleSelect).not.toHaveTextContent(/administrator/i);
  });

  it('validates scope and omits role from scope-only edits', async () => {
    const user = userEvent.setup();
    renderWithProviders(<StaffAccountsPage />);
    await screen.findByText('Road Operator');
    await user.click(screen.getByRole('button', { name: 'Create account' }));
    expect(createStaffAccount).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button', { name: 'Edit access' }));
    await user.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() =>
      expect(updateStaffAccount).toHaveBeenCalledWith(account.staffId, {
        municipalityId: BEIRUT,
        departmentIds: [ROADS],
      }),
    );
  });

  it('confirms activation changes and reports stale/conflict failures', async () => {
    const user = userEvent.setup();
    renderWithProviders(<StaffAccountsPage />);
    await screen.findByText('Road Operator');
    await user.click(screen.getByRole('button', { name: 'Deactivate' }));
    expect(window.confirm).toHaveBeenCalledWith(
      'Deactivate Road Operator? They will no longer be able to sign in.',
    );
    expect(setStaffAccountActive).toHaveBeenCalledWith(account.staffId, false);
  });
});

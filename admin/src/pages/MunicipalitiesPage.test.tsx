import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/render';
import { MunicipalitiesPage } from '@/pages/MunicipalitiesPage';
import {
  createMunicipality,
  listMunicipalities,
  provisionMunicipalityAdmin,
  type MunicipalityProfile,
} from '@/services/municipalities';

vi.mock('@/services/municipalities', () => ({
  listMunicipalities: vi.fn(),
  createMunicipality: vi.fn(),
  updateMunicipality: vi.fn(),
  provisionMunicipalityAdmin: vi.fn(),
  previewMunicipalityRouting: vi.fn(),
  overrideTicketMunicipality: vi.fn(),
}));

vi.mock('@/components/GlobalSearch', () => ({ GlobalSearch: () => null }));
vi.mock('@/components/StaffAssistantPanel', () => ({ StaffAssistantPanel: () => null }));

const beirut: MunicipalityProfile = {
  municipalityId: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  name: 'Beirut Municipality',
  legalName: 'Municipality of Beirut',
  description: 'General municipal services for Beirut.',
  city: 'Beirut',
  governorate: 'Beirut',
  serviceDomains: ['roads', 'waste'],
  bounds: {
    minLatitude: 33.84,
    maxLatitude: 33.93,
    minLongitude: 35.45,
    maxLongitude: 35.58,
  },
  active: true,
  profileVersion: 1,
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
};

function installOperatorSession() {
  window.localStorage.setItem(
    'baladiguard.staffSession',
    JSON.stringify({
      username: 'operator',
      name: 'Demo Developer Operator',
      staffId: 'staff_ops_001',
      role: 'developer_operator',
      municipalityId: null,
      departmentIds: null,
      signedInAt: '2026-08-19T08:00:00Z',
      accessToken: 'test-ops-token',
    }),
  );
}

describe('MunicipalitiesPage', () => {
  beforeEach(() => {
    window.localStorage.clear();
    installOperatorSession();
    vi.clearAllMocks();
    vi.mocked(listMunicipalities).mockResolvedValue([beirut]);
    vi.mocked(createMunicipality).mockResolvedValue({
      ...beirut,
      municipalityId: 'ffffffff-ffff-4fff-8fff-ffffffffffff',
      name: 'Sidon Municipality',
    });
    vi.mocked(provisionMunicipalityAdmin).mockResolvedValue({
      staffId: 'staff_new_admin',
      username: 'sidon.admin',
      municipalityId: beirut.municipalityId,
      role: 'administrator',
    });
  });

  it('lists seeded municipalities for developer operators', async () => {
    renderWithProviders(<MunicipalitiesPage />, { route: '/ops/municipalities' });
    expect(await screen.findByRole('heading', { name: 'Beirut Municipality' })).toBeInTheDocument();
    expect(screen.getByText(/roads, waste/i)).toBeInTheDocument();
  });

  it('provisions the first administrator for a municipality', async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderWithProviders(<MunicipalitiesPage />, { route: '/ops/municipalities' });
    await screen.findByRole('heading', { name: 'Beirut Municipality' });

    await user.selectOptions(screen.getAllByLabelText('Municipality')[0], beirut.municipalityId);
    await user.type(screen.getByLabelText('Username'), 'sidon.admin');
    await user.type(screen.getByLabelText('Full name'), 'Sidon Admin');
    await user.type(screen.getByLabelText('Email'), 'sidon@example.test');
    await user.type(screen.getByLabelText('Initial password'), 'secret-pass');
    await user.click(screen.getByRole('button', { name: 'Create administrator' }));

    expect(confirm).toHaveBeenCalledWith(
      'Create a municipality administrator account with this password?',
    );
    await waitFor(() => {
      expect(provisionMunicipalityAdmin).toHaveBeenCalledWith(beirut.municipalityId, {
        username: 'sidon.admin',
        name: 'Sidon Admin',
        email: 'sidon@example.test',
        password: 'secret-pass',
      });
    });
    confirm.mockRestore();
  });

  it('does not provision an administrator when the confirm is cancelled', async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    renderWithProviders(<MunicipalitiesPage />, { route: '/ops/municipalities' });
    await screen.findByRole('heading', { name: 'Beirut Municipality' });

    await user.selectOptions(screen.getAllByLabelText('Municipality')[0], beirut.municipalityId);
    await user.type(screen.getByLabelText('Username'), 'sidon.admin');
    await user.type(screen.getByLabelText('Full name'), 'Sidon Admin');
    await user.type(screen.getByLabelText('Email'), 'sidon@example.test');
    await user.type(screen.getByLabelText('Initial password'), 'secret-pass');
    await user.click(screen.getByRole('button', { name: 'Create administrator' }));

    expect(provisionMunicipalityAdmin).not.toHaveBeenCalled();
    confirm.mockRestore();
  });
});

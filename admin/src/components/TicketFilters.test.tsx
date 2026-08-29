import { screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';

import { TicketFilters } from '@/components/TicketFilters';
import { renderWithProviders } from '@/test/render';

const ROADS = 'd1111111-1111-1111-1111-111111111111';

function installScopedSession() {
  window.localStorage.setItem(
    'baladiguard.staffSession',
    JSON.stringify({
      username: 'staff',
      name: 'Demo Municipal Staff',
      staffId: 'staff_muni_001',
      role: 'municipal_staff',
      municipalityId: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
      departmentIds: [ROADS],
      signedInAt: '2026-07-27T08:00:00Z',
      accessToken: 'test-staff-token',
    }),
  );
}

describe('TicketFilters', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('limits the department filter to the signed-in staff scope', () => {
    installScopedSession();
    renderWithProviders(
      <TicketFilters
        searchQuery=""
        statusFilter="ALL"
        categoryFilter="ALL"
        urgencyFilter="ALL"
        departmentFilter="ALL"
        categoryOptions={[]}
        resultCount={0}
        totalCount={0}
        onSearchChange={() => undefined}
        onStatusChange={() => undefined}
        onCategoryChange={() => undefined}
        onUrgencyChange={() => undefined}
        onDepartmentChange={() => undefined}
        onClearFilters={() => undefined}
      />,
    );

    const departmentSelect = screen.getByLabelText('Department');
    const options = within(departmentSelect)
      .getAllByRole('option')
      .map((option) => option.textContent);
    expect(options).toContain('All departments');
    expect(options).toContain('Road Maintenance');
    expect(options).not.toContain('Waste Management');
  });
});

import { act, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TicketAssignmentHistory } from '@/components/TicketAssignmentHistory';
import { resetLocaleForTests, setLocale, t } from '@/i18n';
import { fetchAssignmentHistory } from '@/services/tickets';
import { renderWithProviders } from '@/test/render';

vi.mock('@/services/tickets', () => ({
  fetchAssignmentHistory: vi.fn(),
}));

describe('TicketAssignmentHistory', () => {
  beforeEach(() => {
    resetLocaleForTests();
    vi.mocked(fetchAssignmentHistory).mockResolvedValue({
      ticketId: 'tkt_road',
      items: [
        {
          eventId: 'aud_1',
          actionType: 'DEPARTMENT_ASSIGN',
          actorId: 'staff_1',
          actorRole: 'municipal_staff',
          previousValue: null,
          newValue: 'roads',
          summary: 'Department assignment changed from unassigned to roads.',
          occurredAt: '2026-08-22T10:00:00Z',
        },
      ],
    });
  });

  it('shows assignment events and localizes the heading', async () => {
    renderWithProviders(<TicketAssignmentHistory ticketId="tkt_road" />);
    expect(await screen.findByText('Assignment history')).toBeInTheDocument();
    expect(
      screen.getByText(/Department assignment changed from unassigned to roads/),
    ).toBeInTheDocument();

    await act(async () => {
      setLocale('ar');
    });
    expect(screen.getByText(t('ticket.assignmentHistory.title'))).toBeInTheDocument();

    await act(async () => {
      setLocale('fr');
    });
    expect(screen.getByText(t('ticket.assignmentHistory.title'))).toBeInTheDocument();
  });
});

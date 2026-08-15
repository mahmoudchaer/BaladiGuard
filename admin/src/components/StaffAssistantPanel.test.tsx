import { useState } from 'react';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { StaffAssistantPanel } from '@/components/StaffAssistantPanel';
import { queryStaffAssistant } from '@/services/staffAssistant';
import { renderWithProviders } from '@/test/render';
import type { StaffAssistantResponse } from '@/types/staffAssistant';

vi.mock('@/services/staffAssistant', () => ({
  queryStaffAssistant: vi.fn(),
}));

const priorityAnswer: StaffAssistantResponse = {
  intent: 'high_priority_summary',
  asOf: '2026-08-15T12:00:00Z',
  message: '2 accessible high-priority or critical ticket(s) in the open operational queue.',
  count: 2,
  categories: { road_damage: 2 },
  statuses: { IN_PROGRESS: 2 },
  departments: {},
  areas: {},
  areaClusters: [],
  areaClusterTotal: 0,
  areaClustersTruncated: false,
  unlocatedCount: 0,
  incompleteCount: 1,
  tickets: [
    {
      ticketId: 'tkt_1',
      ticketNumber: 'BG-2026-0001',
      status: 'IN_PROGRESS',
      category: 'road_damage',
      priority: 'critical',
      slaState: 'overdue',
      municipalityId: null,
      departmentId: null,
      cellId: null,
      duplicateGroupId: null,
    },
  ],
  appliedFilters: { urgency: 'high,critical', openOnly: 'true' },
};

describe('StaffAssistantPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('asks the real assistant and drills into the ticket list with safe filters', async () => {
    vi.mocked(queryStaffAssistant).mockResolvedValue(priorityAnswer);
    const user = userEvent.setup();
    renderWithProviders(<StaffAssistantPanel open onClose={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'Show high-priority tickets' }));
    expect(await screen.findByText(/2 matching records/i)).toBeInTheDocument();
    expect(screen.getByText(/still pending classification/i)).toBeInTheDocument();
    expect(queryStaffAssistant).toHaveBeenCalledWith('Show high-priority tickets');

    await user.click(screen.getByRole('button', { name: 'View matching tickets' }));
    expect(window.location.search).toContain('urgency=high%2Ccritical');
    expect(window.location.search).toContain('openOnly=true');
    expect(window.location.search).not.toContain('phone');
  });

  it('shows retryable failure and empty unsupported answers', async () => {
    vi.mocked(queryStaffAssistant)
      .mockRejectedValueOnce(new Error('Assistant timed out.'))
      .mockResolvedValueOnce({
        ...priorityAnswer,
        intent: 'unsupported',
        count: 0,
        message: 'I can summarize high-priority tickets or repeated problems by area.',
        tickets: [],
        appliedFilters: {},
      });
    const user = userEvent.setup();
    renderWithProviders(<StaffAssistantPanel open onClose={vi.fn()} />);

    await user.type(screen.getByLabelText('Ask a supported question'), 'delete ticket');
    await user.keyboard('{Enter}');
    expect(await screen.findByRole('alert')).toHaveTextContent('Assistant timed out.');

    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText(/No matching operational records/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'View matching tickets' })).not.toBeInTheDocument();
  });

  it('closes on Escape', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<StaffAssistantPanel open onClose={onClose} />);
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalled();
  });

  function AssistantHarness() {
    const [open, setOpen] = useState(false);
    return (
      <>
        <button type="button" onClick={() => setOpen(true)}>
          Assistant
        </button>
        <StaffAssistantPanel open={open} onClose={() => setOpen(false)} />
      </>
    );
  }

  it('traps Tab and Shift+Tab inside the dialog', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AssistantHarness />);
    await user.click(screen.getByRole('button', { name: 'Assistant' }));
    const dialog = screen.getByRole('dialog', { name: 'Staff assistant' });
    const closeButton = screen.getByRole('button', { name: 'Close' });
    const input = screen.getByLabelText('Ask a supported question');
    const lastSuggestion = screen.getByRole('button', { name: 'وين المشاكل المتكررة؟' });

    expect(input).toHaveFocus();
    await user.tab({ shift: true });
    expect(closeButton).toHaveFocus();
    await user.tab({ shift: true });
    expect(lastSuggestion).toHaveFocus();
    await user.tab();
    expect(closeButton).toHaveFocus();
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it('restores focus to the Assistant trigger on Escape and Close', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AssistantHarness />);
    const trigger = screen.getByRole('button', { name: 'Assistant' });

    await user.click(trigger);
    expect(screen.getByRole('dialog', { name: 'Staff assistant' })).toBeInTheDocument();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Staff assistant' })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();

    await user.click(trigger);
    await user.click(screen.getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog', { name: 'Staff assistant' })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});

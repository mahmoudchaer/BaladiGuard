import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  assignTicketDepartment,
  createTicketComment,
  fetchTicketActivity,
  fetchTicketComments,
  reviewTicketCategory,
  fetchTicketById,
  fetchTickets,
  mergeDuplicateTickets,
} from '@/services/tickets';
import { renderWithProviders } from '@/test/render';
import type { Ticket } from '@/types/ticket';
import { TicketDetailPage } from '@/pages/TicketDetailPage';

vi.mock('@/services/tickets', () => ({
  fetchTicketById: vi.fn(),
  fetchTickets: vi.fn(),
  fetchTicketActivity: vi.fn(),
  fetchTicketComments: vi.fn(),
  createTicketComment: vi.fn(),
  mergeDuplicateTickets: vi.fn(),
  reviewTicketCategory: vi.fn(),
  updateTicketStatus: vi.fn(),
  assignTicketDepartment: vi.fn(),
}));

vi.mock('@/components/TicketMap', () => ({
  TicketMap: ({ tickets }: { tickets: Ticket[] }) => (
    <div data-testid="ticket-map">Map with {tickets.length} pins</div>
  ),
}));

const ticket: Ticket = {
  ticketId: 'tkt_123',
  ticketNumber: 'BG-2026-0001',
  trackingCode: 'ABC123',
  description: 'Large pothole near the university gate.',
  contact: {},
  location: {
    latitude: 33.896,
    longitude: 35.478,
    addressText: 'Hamra, Beirut',
    source: 'GPS',
  },
  imageObjectKey: 'reports/tkt_123.jpg',
  status: 'UNDER_REVIEW',
  category: 'PENDING_CLASSIFICATION',
  priority: null,
  createdBy: null,
  municipalityId: null,
  departmentId: 'd1111111-1111-1111-1111-111111111111',
  departmentName: 'Road Maintenance',
  duplicateGroupId: null,
  duplicateSuggestions: [],
  createdAt: '2026-07-17T08:00:00Z',
  updatedAt: '2026-07-17T08:01:00Z',
  ai: {
    originalDescription: 'Large pothole near the university gate.',
    aiSuggestedCategory: 'road_damage',
    aiCategoryExplanation: 'The report describes damage to a public road.',
    aiConfidence: 0.92,
    aiProcessingStatus: 'completed',
    suggestedDepartmentId: 'd1111111-1111-1111-1111-111111111111',
    urgencyScore: 62,
    urgencyReason: 'High (62): possible injury or collision risk; critical location.',
  },
};

function renderPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/tickets/:ticketId" element={<TicketDetailPage />} />
    </Routes>,
    { route: '/tickets/tkt_123' },
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchTicketById).mockResolvedValue(ticket);
  vi.mocked(fetchTickets).mockResolvedValue([]);
  vi.mocked(fetchTicketActivity).mockResolvedValue({ events: [], nextCursor: null });
  vi.mocked(fetchTicketComments).mockResolvedValue([]);
});

describe('TicketDetailPage duplicate suggestions', () => {
  it('shows possible duplicate ticket details and links to the suggested ticket', async () => {
    vi.mocked(fetchTicketById).mockResolvedValue({
      ...ticket,
      duplicateSuggestions: [
        {
          ticketId: 'tkt_duplicate',
          ticketNumber: 'BG-2026-0201',
          distanceMeters: 42.4,
          status: 'IN_PROGRESS',
          category: 'waste',
        },
      ],
    });
    renderPage();

    expect(await screen.findByText('Possible duplicates')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'BG-2026-0201' })).toHaveAttribute(
      'href',
      '/tickets/tkt_duplicate',
    );
    expect(screen.getByText('42 m away')).toBeInTheDocument();
    expect(screen.getByText('In Progress')).toBeInTheDocument();
    expect(screen.getAllByText('Waste').length).toBeGreaterThan(0);
  });

  it('shows an empty state when no duplicate suggestions exist', async () => {
    renderPage();

    expect(await screen.findByText('No possible duplicate tickets found.')).toBeInTheDocument();
  });

  it('shows a classification-needed state before duplicate suggestions are available', async () => {
    vi.mocked(fetchTicketById).mockResolvedValue({
      ...ticket,
      ai: { originalDescription: ticket.description, aiProcessingStatus: 'pending' },
    });
    renderPage();

    expect(
      await screen.findByText(
        'Duplicate suggestions are available once this ticket is classified.',
      ),
    ).toBeInTheDocument();
  });
});

describe('TicketDetailPage states', () => {
  it('shows a loading state while the ticket detail is fetched', () => {
    vi.mocked(fetchTicketById).mockReturnValue(new Promise(() => undefined));

    renderPage();

    expect(screen.getByText('Loading ticket details…')).toBeInTheDocument();
  });

  it('shows a not-found state when the ticket does not exist', async () => {
    vi.mocked(fetchTicketById).mockResolvedValue(null);

    renderPage();

    expect(await screen.findByText('Ticket not found')).toBeInTheDocument();
    expect(screen.getByText(/This ticket may have been removed/)).toBeInTheDocument();
  });

  it('shows an error state when the ticket detail request fails', async () => {
    vi.mocked(fetchTicketById).mockRejectedValue(new Error('Ticket service unavailable.'));

    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load ticket');
    expect(screen.getByText('Ticket service unavailable.')).toBeInTheDocument();
  });
});

describe('TicketDetailPage category review', () => {
  it('shows the stored AI suggestion and explanation', async () => {
    renderPage();

    expect(await screen.findByText('AI category recommendation')).toBeInTheDocument();
    expect(screen.getByText('Next action')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Complete staff review, then move the ticket to the responsible department.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByText('The report describes damage to a public road.')).toBeInTheDocument();
    expect(screen.getByText('Confidence 92%')).toBeInTheDocument();
    expect(screen.getByText('62/100')).toBeInTheDocument();
    expect(screen.getByText('Urgency reason')).toBeInTheDocument();
    expect(
      screen.getByText('High (62): possible injury or collision risk; critical location.'),
    ).toBeInTheDocument();
  });

  it('accepts the AI suggestion and immediately shows the review result', async () => {
    const user = userEvent.setup();
    vi.mocked(reviewTicketCategory).mockResolvedValue({
      ...ticket,
      category: 'road_damage',
      updatedAt: '2026-07-17T08:05:00Z',
      ai: {
        ...ticket.ai,
        finalCategory: 'road_damage',
        categoryReviewedBy: 'staff-1',
        categoryReviewedAt: '2026-07-17T08:05:00Z',
      },
    });
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Accept AI suggestion' }));

    expect(reviewTicketCategory).toHaveBeenCalledWith('tkt_123', {
      finalCategory: 'road_damage',
    });
    expect(await screen.findByText('Reviewed')).toBeInTheDocument();
    expect(screen.getByText(/Reviewed by staff-1 on/)).toBeInTheDocument();
  });

  it('saves a corrected category while keeping the original suggestion visible', async () => {
    const user = userEvent.setup();
    vi.mocked(reviewTicketCategory).mockResolvedValue({
      ...ticket,
      category: 'waste',
      updatedAt: '2026-07-17T08:05:00Z',
      ai: {
        ...ticket.ai,
        finalCategory: 'waste',
        categoryReviewedAt: '2026-07-17T08:05:00Z',
      },
    });
    renderPage();

    const select = await screen.findByLabelText('Final category');
    await user.selectOptions(select, 'waste');
    await user.click(screen.getByRole('button', { name: 'Save final category' }));

    expect(reviewTicketCategory).toHaveBeenCalledWith('tkt_123', {
      finalCategory: 'waste',
    });
    expect(await screen.findByText('Reviewed')).toBeInTheDocument();
    expect(screen.getByText('AI suggestion')).toBeInTheDocument();
    expect(screen.getAllByText('Road Damage').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Waste').length).toBeGreaterThan(0);
  });

  it('disables review controls while AI processing is pending', async () => {
    vi.mocked(fetchTicketById).mockResolvedValue({
      ...ticket,
      ai: {
        originalDescription: ticket.description,
        aiProcessingStatus: 'pending',
      },
    });
    renderPage();

    expect(await screen.findByText(/AI processing is still in progress/)).toBeInTheDocument();
    expect(screen.getByLabelText('Final category')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Save final category' })).toBeDisabled();
  });

  it('shows a saving state and prevents duplicate submissions', async () => {
    const user = userEvent.setup();
    let resolveReview!: (value: Ticket | null) => void;
    vi.mocked(reviewTicketCategory).mockReturnValue(
      new Promise((resolve) => {
        resolveReview = resolve;
      }),
    );
    renderPage();

    const select = await screen.findByLabelText('Final category');
    await user.selectOptions(select, 'waste');
    await user.click(screen.getByRole('button', { name: 'Save final category' }));

    expect(screen.getByRole('button', { name: 'Saving category...' })).toBeDisabled();
    expect(select).toBeDisabled();
    expect(reviewTicketCategory).toHaveBeenCalledTimes(1);

    resolveReview({
      ...ticket,
      category: 'waste',
      ai: {
        ...ticket.ai,
        finalCategory: 'waste',
        categoryReviewedAt: '2026-07-17T08:05:00Z',
      },
    });
    expect(await screen.findByText('Reviewed')).toBeInTheDocument();
  });

  it('shows API errors without discarding the loaded ticket', async () => {
    const user = userEvent.setup();
    vi.mocked(reviewTicketCategory).mockRejectedValue(new Error('Unable to save category review.'));
    renderPage();

    const select = await screen.findByLabelText('Final category');
    await user.selectOptions(select, 'waste');
    await user.click(screen.getByRole('button', { name: 'Save final category' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to save category review.');
    expect(screen.getByText('AI category recommendation')).toBeInTheDocument();
  });
});

function buildCandidate(overrides: Partial<Ticket>): Ticket {
  return {
    ...ticket,
    ticketId: 'tkt_candidate',
    ticketNumber: 'BG-2026-0099',
    ...overrides,
  };
}

describe('TicketDetailPage duplicate merge', () => {
  it('only offers ungrouped candidates that share the effective category', async () => {
    vi.mocked(fetchTickets).mockResolvedValue([
      buildCandidate({
        ticketId: 'tkt_same_category',
        ticketNumber: 'BG-2026-0201',
        ai: { aiSuggestedCategory: 'road_damage' },
      }),
      buildCandidate({
        ticketId: 'tkt_other_category',
        ticketNumber: 'BG-2026-0202',
        ai: { aiSuggestedCategory: 'waste' },
      }),
      buildCandidate({
        ticketId: 'tkt_already_grouped',
        ticketNumber: 'BG-2026-0203',
        duplicateGroupId: 'dup_existing',
        ai: { aiSuggestedCategory: 'road_damage' },
      }),
      buildCandidate({
        ticketId: 'tkt_pending',
        ticketNumber: 'BG-2026-0204',
        ai: { aiProcessingStatus: 'pending' },
      }),
    ]);
    renderPage();

    expect(await screen.findByText('BG-2026-0201')).toBeInTheDocument();
    expect(screen.queryByText('BG-2026-0202')).not.toBeInTheDocument();
    expect(screen.queryByText('BG-2026-0203')).not.toBeInTheDocument();
    expect(screen.queryByText('BG-2026-0204')).not.toBeInTheDocument();
  });

  it('does not offer merge for tickets that are still pending classification', async () => {
    vi.mocked(fetchTicketById).mockResolvedValue({
      ...ticket,
      ai: { originalDescription: ticket.description, aiProcessingStatus: 'pending' },
    });
    renderPage();

    expect(await screen.findByText(/no reviewed or AI-suggested category yet/)).toBeInTheDocument();
    expect(fetchTickets).not.toHaveBeenCalled();
    expect(
      screen.queryByRole('button', { name: 'Merge selected as duplicates' }),
    ).not.toBeInTheDocument();
  });

  it('merges selected duplicates under the open ticket', async () => {
    const user = userEvent.setup();
    const candidate = buildCandidate({
      ticketId: 'tkt_same_category',
      ticketNumber: 'BG-2026-0201',
      ai: { aiSuggestedCategory: 'road_damage' },
    });
    vi.mocked(fetchTickets).mockResolvedValue([candidate]);
    vi.mocked(mergeDuplicateTickets).mockResolvedValue({
      ...ticket,
      duplicateGroupId: 'dup_new',
      duplicateGroup: {
        duplicateGroupId: 'dup_new',
        ticketIds: [ticket.ticketId, candidate.ticketId],
        canonicalTicketId: ticket.ticketId,
      },
    });
    renderPage();

    await user.click(await screen.findByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: 'Merge selected as duplicates' }));

    expect(mergeDuplicateTickets).toHaveBeenCalledWith({
      canonicalTicketId: ticket.ticketId,
      duplicateTicketIds: [candidate.ticketId],
    });
    expect(await screen.findByText(/grouped as the main report/)).toBeInTheDocument();
  });

  it('lets the main ticket of a group add more duplicates', async () => {
    vi.mocked(fetchTicketById).mockResolvedValue({
      ...ticket,
      duplicateGroupId: 'dup_existing',
      duplicateGroup: {
        duplicateGroupId: 'dup_existing',
        ticketIds: [ticket.ticketId, 'tkt_member'],
        canonicalTicketId: ticket.ticketId,
      },
    });
    renderPage();

    expect(await screen.findByText(/grouped as the main report/)).toBeInTheDocument();
    expect(
      screen.getByText('Add more same-category tickets to this duplicate group.'),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Merge selected as duplicates' }),
    ).toBeInTheDocument();
  });

  it('hides merge controls for non-main group members', async () => {
    vi.mocked(fetchTicketById).mockResolvedValue({
      ...ticket,
      duplicateGroupId: 'dup_existing',
      duplicateGroup: {
        duplicateGroupId: 'dup_existing',
        ticketIds: ['tkt_main', ticket.ticketId],
        canonicalTicketId: 'tkt_main',
      },
    });
    renderPage();

    expect(await screen.findByText(/This ticket is grouped/)).toBeInTheDocument();
    expect(screen.getByText('Add further duplicates from the main ticket.')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Merge selected as duplicates' }),
    ).not.toBeInTheDocument();
  });
});

describe('TicketDetailPage location map', () => {
  it('shows a map pin and Google Maps link for the ticket location', async () => {
    renderPage();

    expect(await screen.findByTestId('ticket-map')).toHaveTextContent('Map with 1 pins');
    const mapsLink = screen.getByRole('link', { name: 'Open in Google Maps' });
    expect(mapsLink).toHaveAttribute('href', 'https://www.google.com/maps?q=33.896000,35.478000');
    expect(mapsLink).toHaveAttribute('target', '_blank');
  });
});

describe('TicketDetailPage department assignment', () => {
  it('shows the suggested department only when it differs from the assigned one', async () => {
    vi.mocked(fetchTicketById).mockResolvedValue({
      ...ticket,
      departmentId: 'd3333333-3333-3333-3333-333333333333',
      departmentName: 'Street Lighting',
      ai: {
        ...ticket.ai,
        suggestedDepartmentId: 'd1111111-1111-1111-1111-111111111111',
      },
    });
    renderPage();

    expect(await screen.findByLabelText('Assigned department')).toHaveValue(
      'd3333333-3333-3333-3333-333333333333',
    );
    expect(document.querySelector('.ticket-detail__department')).toHaveTextContent(
      'Street Lighting',
    );
    expect(screen.getByText(/Suggested:\s*Road Maintenance/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Accept suggested department' })).toBeInTheDocument();
  });

  it('hides the suggestion row when suggested and assigned match', async () => {
    renderPage();

    expect(await screen.findByLabelText('Assigned department')).toBeInTheDocument();
    expect(screen.queryByText(/Suggested:/)).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Accept suggested department' }),
    ).not.toBeInTheDocument();
  });

  it('saves a department override while preserving the suggestion in the UI', async () => {
    const user = userEvent.setup();
    vi.mocked(assignTicketDepartment).mockResolvedValue({
      ...ticket,
      departmentId: 'd2222222-2222-2222-2222-222222222222',
      departmentName: 'Waste Management',
      updatedBy: 'staff',
      updatedAt: '2026-07-17T09:00:00Z',
      ai: {
        ...ticket.ai,
        suggestedDepartmentId: 'd1111111-1111-1111-1111-111111111111',
      },
    });
    vi.mocked(fetchTicketById).mockResolvedValue({
      ...ticket,
      ai: {
        ...ticket.ai,
        suggestedDepartmentId: 'd1111111-1111-1111-1111-111111111111',
      },
    });

    renderPage();

    const select = await screen.findByLabelText('Assigned department');
    await user.selectOptions(select, 'd2222222-2222-2222-2222-222222222222');
    await user.click(screen.getByRole('button', { name: 'Save department' }));

    expect(assignTicketDepartment).toHaveBeenCalledWith('tkt_123', {
      departmentId: 'd2222222-2222-2222-2222-222222222222',
      updatedBy: undefined,
    });
    expect(await screen.findByText('Department assignment updated.')).toBeInTheDocument();
    expect(screen.getByLabelText('Assigned department')).toHaveValue(
      'd2222222-2222-2222-2222-222222222222',
    );
    expect(document.querySelector('.ticket-detail__department')).toHaveTextContent(
      'Waste Management',
    );
    expect(screen.getByText(/Suggested:\s*Road Maintenance/)).toBeInTheDocument();
    expect(screen.getByText(/Last updated by staff/)).toBeInTheDocument();
  });

  it('accepts the suggested department without changing the suggestion label', async () => {
    const user = userEvent.setup();
    vi.mocked(fetchTicketById).mockResolvedValue({
      ...ticket,
      departmentId: 'd3333333-3333-3333-3333-333333333333',
      departmentName: 'Street Lighting',
      ai: {
        ...ticket.ai,
        suggestedDepartmentId: 'd1111111-1111-1111-1111-111111111111',
      },
    });
    vi.mocked(assignTicketDepartment).mockResolvedValue({
      ...ticket,
      departmentId: 'd1111111-1111-1111-1111-111111111111',
      departmentName: 'Road Maintenance',
      updatedBy: 'staff',
      ai: {
        ...ticket.ai,
        suggestedDepartmentId: 'd1111111-1111-1111-1111-111111111111',
      },
    });

    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Accept suggested department' }));

    expect(assignTicketDepartment).toHaveBeenCalledWith('tkt_123', {
      departmentId: 'd1111111-1111-1111-1111-111111111111',
      updatedBy: undefined,
    });
    expect(await screen.findByText('Department assignment updated.')).toBeInTheDocument();
    expect(screen.getByLabelText('Assigned department')).toHaveValue(
      'd1111111-1111-1111-1111-111111111111',
    );
    expect(screen.queryByText(/Suggested:/)).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Accept suggested department' }),
    ).not.toBeInTheDocument();
  });

  it('disables controls while saving and does not double-submit', async () => {
    const user = userEvent.setup();
    let resolveSave: ((value: Ticket) => void) | undefined;
    vi.mocked(assignTicketDepartment).mockImplementationOnce(
      () =>
        new Promise<Ticket>((resolve) => {
          resolveSave = resolve;
        }),
    );

    renderPage();

    const select = await screen.findByLabelText('Assigned department');
    await user.selectOptions(select, 'd2222222-2222-2222-2222-222222222222');
    await user.click(screen.getByRole('button', { name: 'Save department' }));

    expect(screen.getByRole('button', { name: 'Saving department...' })).toBeDisabled();
    expect(screen.getByLabelText('Assigned department')).toBeDisabled();
    expect(screen.getByText('Saving department assignment...')).toBeInTheDocument();
    expect(assignTicketDepartment).toHaveBeenCalledTimes(1);

    resolveSave?.({
      ...ticket,
      departmentId: 'd2222222-2222-2222-2222-222222222222',
      departmentName: 'Waste Management',
    });

    expect(await screen.findByRole('button', { name: 'Save department' })).toBeDisabled();
  });

  it('shows an error and reverts the select when the API fails', async () => {
    const user = userEvent.setup();
    vi.mocked(assignTicketDepartment).mockRejectedValue(
      new Error('Unable to update ticket department.'),
    );

    renderPage();

    const select = await screen.findByLabelText('Assigned department');
    expect(select).toHaveValue('d1111111-1111-1111-1111-111111111111');
    await user.selectOptions(select, 'd2222222-2222-2222-2222-222222222222');
    await user.click(screen.getByRole('button', { name: 'Save department' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to update ticket department.',
    );
    expect(screen.getByLabelText('Assigned department')).toHaveValue(
      'd1111111-1111-1111-1111-111111111111',
    );
    expect(document.querySelector('.ticket-detail__department')).toHaveTextContent(
      'Road Maintenance',
    );
  });

  it('does not call the API when re-saving the current department', async () => {
    renderPage();

    expect(await screen.findByLabelText('Assigned department')).toHaveValue(
      'd1111111-1111-1111-1111-111111111111',
    );
    expect(screen.getByRole('button', { name: 'Save department' })).toBeDisabled();
    expect(assignTicketDepartment).not.toHaveBeenCalled();
  });
});

describe('TicketDetailPage internal activity', () => {
  it('keeps a successfully posted comment when the activity refresh fails', async () => {
    const user = userEvent.setup();
    vi.mocked(createTicketComment).mockResolvedValue({
      commentId: 'cmt_1',
      ticketId: ticket.ticketId,
      authorStaffId: 'staff_admin_001',
      authorDisplayName: 'Administrator',
      text: 'Please inspect the road closure.',
      mentionedStaffIds: [],
      createdAt: '2026-07-17T08:05:00Z',
    });
    vi.mocked(fetchTicketActivity)
      .mockResolvedValueOnce({ events: [], nextCursor: null })
      .mockRejectedValueOnce(new Error('Activity refresh failed.'));

    renderPage();
    await user.type(
      await screen.findByLabelText('Add internal comment'),
      'Please inspect the road closure.',
    );
    await user.click(screen.getByRole('button', { name: 'Post comment' }));

    expect(await screen.findByText('Please inspect the road closure.')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Activity refresh failed.');
  });
});

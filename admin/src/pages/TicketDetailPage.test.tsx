import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  assignTicketDepartment,
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

type TestUser = ReturnType<typeof userEvent.setup>;

function renderPage(route = '/tickets/tkt_123') {
  return renderWithProviders(
    <Routes>
      <Route path="/tickets/:ticketId" element={<TicketDetailPage />} />
    </Routes>,
    { route },
  );
}

async function openSection(user: TestUser, name: RegExp | string) {
  await user.click(await screen.findByRole('tab', { name }));
}

function buildCandidate(overrides: Partial<Ticket>): Ticket {
  return {
    ...ticket,
    ticketId: 'tkt_candidate',
    ticketNumber: 'BG-2026-0099',
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchTicketById).mockResolvedValue(ticket);
  vi.mocked(fetchTickets).mockResolvedValue([]);
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

describe('TicketDetailPage summary header', () => {
  it('shows a compact actionable summary with a route back to the queue', async () => {
    renderPage();

    expect(await screen.findByRole('heading', { name: 'BG-2026-0001' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Back to ticket queue/ })).toHaveAttribute('href', '/');
    expect(screen.getByText('Road Maintenance')).toBeInTheDocument();
    expect(screen.getAllByText('Road Damage').length).toBeGreaterThan(0);
    expect(screen.getByText('Age')).toBeInTheDocument();
  });

  it('keeps technical identifiers inside a collapsed technical disclosure', async () => {
    renderPage();

    const summary = await screen.findByText('Technical details');
    const disclosure = summary.closest('details');
    expect(disclosure).not.toBeNull();
    expect(disclosure).not.toHaveAttribute('open');

    const technical = within(disclosure as HTMLElement);
    expect(technical.getByText('ABC123')).toBeInTheDocument();
    expect(technical.getByText('tkt_123')).toBeInTheDocument();
    expect(technical.getByText('reports/tkt_123.jpg')).toBeInTheDocument();
  });

  it('moves staff to the review section from the primary summary action', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Review & update ticket' }));

    expect(screen.getByRole('tab', { name: 'Review & Actions' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(screen.getByLabelText('Assigned department')).toBeInTheDocument();
  });
});

describe('TicketDetailPage section navigation', () => {
  it('defaults to the overview section', async () => {
    renderPage();

    expect(await screen.findByRole('tab', { name: 'Overview' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(screen.getByText('Large pothole near the university gate.')).toBeInTheDocument();
  });

  it('opens the deep-linked section from the URL', async () => {
    renderPage('/tickets/tkt_123?section=duplicates');

    expect(await screen.findByRole('tab', { name: /^Duplicates/ })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(screen.getByText('Possible duplicates')).toBeInTheDocument();
  });

  it('falls back to overview for an unknown section value', async () => {
    renderPage('/tickets/tkt_123?section=not-a-section');

    expect(await screen.findByRole('tab', { name: 'Overview' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
  });

  it('records the active section in the URL without refetching the ticket', async () => {
    const user = userEvent.setup();
    renderPage();

    await openSection(user, 'Review & Actions');
    expect(window.location.search).toBe('?section=review');

    await openSection(user, /^Duplicates/);
    expect(window.location.search).toBe('?section=duplicates');

    await openSection(user, 'Activity');
    expect(window.location.search).toBe('?section=activity');

    expect(fetchTicketById).toHaveBeenCalledTimes(1);
    expect(fetchTickets).toHaveBeenCalledTimes(1);
  });

  it('moves between tabs with the keyboard', async () => {
    const user = userEvent.setup();
    renderPage();

    const overviewTab = await screen.findByRole('tab', { name: 'Overview' });
    overviewTab.focus();
    await user.keyboard('{ArrowRight}');

    expect(screen.getByRole('tab', { name: 'Review & Actions' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(screen.getByRole('tab', { name: 'Review & Actions' })).toHaveFocus();
    expect(fetchTicketById).toHaveBeenCalledTimes(1);
  });

  it('revalidates the ticket on explicit refresh and keeps the active section', async () => {
    const user = userEvent.setup();
    renderPage('/tickets/tkt_123?section=activity');

    await user.click(await screen.findByRole('button', { name: 'Refresh' }));

    await waitFor(() => expect(fetchTicketById).toHaveBeenCalledTimes(2));
    expect(screen.getByRole('tab', { name: 'Activity' })).toHaveAttribute('aria-selected', 'true');
    expect(window.location.search).toBe('?section=activity');
  });
});

describe('TicketDetailPage overview', () => {
  it('leads with the citizen description, next action, and photo without raw storage keys', async () => {
    renderPage();

    expect(await screen.findByText('Next action')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Complete staff review, then move the ticket to the responsible department.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByText('Large pothole near the university gate.')).toBeInTheDocument();
    expect(screen.getByText('Report photo unavailable')).toBeInTheDocument();
    expect(document.querySelector('.ticket-photo__fallback-key')).toBeNull();
    expect(document.querySelector('.ticket-photo__caption')).toBeNull();
  });

  it('shows a map pin and Google Maps link for the ticket location', async () => {
    renderPage();

    expect(await screen.findByTestId('ticket-map')).toHaveTextContent('Map with 1 pins');
    const mapsLink = screen.getByRole('link', { name: 'Open in Google Maps' });
    expect(mapsLink).toHaveAttribute('href', 'https://www.google.com/maps?q=33.896000,35.478000');
    expect(mapsLink).toHaveAttribute('target', '_blank');
  });
});

describe('TicketDetailPage category review', () => {
  it('presents the AI suggestion compactly with a single staff-verification disclaimer', async () => {
    renderPage('/tickets/tkt_123?section=review');

    expect(await screen.findByText('Category decision')).toBeInTheDocument();
    expect(
      screen.getAllByText(
        'AI-assisted fields are decision support only. Staff must verify them before acting.',
      ),
    ).toHaveLength(1);
    expect(screen.getByText('The report describes damage to a public road.')).toBeInTheDocument();
    expect(screen.getByText('Confidence 92%')).toBeInTheDocument();
  });

  it('shows urgency compactly and keeps the reasoning behind a disclosure', async () => {
    renderPage('/tickets/tkt_123?section=review');

    expect(await screen.findByText('High · 62/100')).toBeInTheDocument();

    const disclosure = screen.getByText('Why this score?').closest('details');
    expect(disclosure).not.toBeNull();
    expect(disclosure).not.toHaveAttribute('open');
    expect(
      within(disclosure as HTMLElement).getByText(
        'High (62): possible injury or collision risk; critical location.',
      ),
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
    renderPage('/tickets/tkt_123?section=review');

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
    renderPage('/tickets/tkt_123?section=review');

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
    renderPage('/tickets/tkt_123?section=review');

    expect(await screen.findByText(/AI processing is still in progress/)).toBeInTheDocument();
    expect(screen.getByLabelText('Final category')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Save final category' })).toBeDisabled();
  });

  it('keeps the processing and failed AI states visible', async () => {
    vi.mocked(fetchTicketById).mockResolvedValue({
      ...ticket,
      ai: { originalDescription: ticket.description, aiProcessingStatus: 'processing' },
    });
    const { unmount } = renderPage('/tickets/tkt_123?section=review');

    expect(await screen.findByText(/AI processing is running/)).toBeInTheDocument();
    unmount();

    vi.mocked(fetchTicketById).mockResolvedValue({
      ...ticket,
      ai: { originalDescription: ticket.description, aiProcessingStatus: 'failed' },
    });
    renderPage('/tickets/tkt_123?section=review');

    expect(await screen.findByText(/AI could not recommend a category/)).toBeInTheDocument();
  });

  it('shows a saving state and prevents duplicate submissions', async () => {
    const user = userEvent.setup();
    let resolveReview!: (value: Ticket | null) => void;
    vi.mocked(reviewTicketCategory).mockReturnValue(
      new Promise((resolve) => {
        resolveReview = resolve;
      }),
    );
    renderPage('/tickets/tkt_123?section=review');

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
    renderPage('/tickets/tkt_123?section=review');

    const select = await screen.findByLabelText('Final category');
    await user.selectOptions(select, 'waste');
    await user.click(screen.getByRole('button', { name: 'Save final category' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to save category review.');
    expect(screen.getByText('Category decision')).toBeInTheDocument();
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
    renderPage('/tickets/tkt_123?section=review');

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
    renderPage('/tickets/tkt_123?section=review');

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

    renderPage('/tickets/tkt_123?section=review');

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
    expect(fetchTicketById).toHaveBeenCalledTimes(1);
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

    renderPage('/tickets/tkt_123?section=review');

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

    renderPage('/tickets/tkt_123?section=review');

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

    renderPage('/tickets/tkt_123?section=review');

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
    renderPage('/tickets/tkt_123?section=review');

    expect(await screen.findByLabelText('Assigned department')).toHaveValue(
      'd1111111-1111-1111-1111-111111111111',
    );
    expect(screen.getByRole('button', { name: 'Save department' })).toBeDisabled();
    expect(assignTicketDepartment).not.toHaveBeenCalled();
  });
});

describe('TicketDetailPage duplicate candidates', () => {
  it('shows possible duplicate details and links to the suggested ticket', async () => {
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
    renderPage('/tickets/tkt_123?section=duplicates');

    expect(await screen.findByText('Possible duplicates')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'BG-2026-0201' })).toHaveAttribute(
      'href',
      '/tickets/tkt_duplicate',
    );
    expect(screen.getByText('42 m away')).toBeInTheDocument();
    expect(screen.getByText('In Progress')).toBeInTheDocument();
    expect(screen.getAllByText('Waste').length).toBeGreaterThan(0);
    expect(screen.getByText('Suggested match')).toBeInTheDocument();
  });

  it('badges the duplicates tab with the suggestion count', async () => {
    vi.mocked(fetchTicketById).mockResolvedValue({
      ...ticket,
      duplicateSuggestions: [
        {
          ticketId: 'tkt_duplicate_a',
          ticketNumber: 'BG-2026-0201',
          distanceMeters: 42.4,
          status: 'IN_PROGRESS',
          category: 'road_damage',
        },
        {
          ticketId: 'tkt_duplicate_b',
          ticketNumber: 'BG-2026-0202',
          distanceMeters: 120,
          status: 'SUBMITTED',
          category: 'road_damage',
        },
      ],
    });
    renderPage();

    const duplicatesTab = await screen.findByRole('tab', { name: /^Duplicates/ });
    expect(within(duplicatesTab).getByText('2')).toBeInTheDocument();
    expect(duplicatesTab).toHaveAccessibleName('Duplicates, 2 possible duplicates');
  });

  it('shows an empty state when no duplicate candidates exist', async () => {
    renderPage('/tickets/tkt_123?section=duplicates');

    expect(await screen.findByText('No possible duplicate tickets found.')).toBeInTheDocument();
  });

  it('shows a classification-needed state before duplicate suggestions are available', async () => {
    vi.mocked(fetchTicketById).mockResolvedValue({
      ...ticket,
      ai: { originalDescription: ticket.description, aiProcessingStatus: 'pending' },
    });
    renderPage('/tickets/tkt_123?section=duplicates');

    expect(await screen.findByText(/no reviewed or AI-suggested category yet/)).toBeInTheDocument();
    expect(fetchTickets).not.toHaveBeenCalled();
    expect(
      screen.queryByRole('button', { name: 'Merge selected as duplicates' }),
    ).not.toBeInTheDocument();
  });

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
    renderPage('/tickets/tkt_123?section=duplicates');

    expect(await screen.findByText('BG-2026-0201')).toBeInTheDocument();
    expect(screen.queryByText('BG-2026-0202')).not.toBeInTheDocument();
    expect(screen.queryByText('BG-2026-0203')).not.toBeInTheDocument();
    expect(screen.queryByText('BG-2026-0204')).not.toBeInTheDocument();
  });

  it('gives each candidate enough context to make a responsible decision', async () => {
    vi.mocked(fetchTickets).mockResolvedValue([
      buildCandidate({
        ticketId: 'tkt_same_category',
        ticketNumber: 'BG-2026-0201',
        description: 'Deep pothole opposite the campus entrance.',
        priority: 'high',
        location: {
          latitude: 33.8965,
          longitude: 35.4782,
          addressText: 'Bliss Street, Beirut',
          source: 'GPS',
        },
        ai: { aiSuggestedCategory: 'road_damage' },
      }),
    ]);
    renderPage('/tickets/tkt_123?section=duplicates');

    expect(await screen.findByText('BG-2026-0201')).toBeInTheDocument();
    expect(screen.getByText('Deep pothole opposite the campus entrance.')).toBeInTheDocument();
    expect(screen.getByText('Bliss Street, Beirut')).toBeInTheDocument();
    expect(screen.getAllByText('High').length).toBeGreaterThan(0);
    expect(screen.getByText(/m away$/)).toBeInTheDocument();
    expect(
      screen.getByRole('img', { name: 'No photo available for BG-2026-0201' }),
    ).toBeInTheDocument();
  });
});

const comparisonCandidate = buildCandidate({
  ticketId: 'tkt_same_category',
  ticketNumber: 'BG-2026-0201',
  trackingCode: 'XYZ789',
  description: 'Second report about the same pothole.',
  contact: { name: 'Citizen Name', phone: '+96170000000' },
  imageObjectKey: 'reports/tkt_same_category.jpg',
  ai: { aiSuggestedCategory: 'road_damage' },
});

function mockComparisonDetail(candidate: Ticket = comparisonCandidate) {
  vi.mocked(fetchTicketById).mockImplementation(async (requestedId: string) =>
    requestedId === ticket.ticketId ? ticket : candidate,
  );
  vi.mocked(fetchTickets).mockResolvedValue([candidate]);
}

async function findComparisonRegion(candidateNumber = 'BG-2026-0201') {
  return within(
    await screen.findByRole('region', {
      name: `Comparison of ${candidateNumber} with BG-2026-0001`,
    }),
  );
}

function queryComparisonRegion(candidateNumber = 'BG-2026-0201') {
  return screen.queryByRole('region', {
    name: `Comparison of ${candidateNumber} with BG-2026-0001`,
  });
}

describe('TicketDetailPage duplicate comparison', () => {
  it('keeps expanding a candidate separate from selecting it', async () => {
    const user = userEvent.setup();
    mockComparisonDetail();
    renderPage('/tickets/tkt_123?section=duplicates');

    const checkbox = await screen.findByRole('checkbox', {
      name: 'Select BG-2026-0201 as a duplicate',
    });
    const expandButton = screen.getByRole('button', { name: 'Compare BG-2026-0201' });

    await user.click(expandButton);
    expect(checkbox).not.toBeChecked();
    const comparison = await findComparisonRegion();
    expect(
      await comparison.findByText('Second report about the same pothole.'),
    ).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Hide comparison for BG-2026-0201' }));
    await user.click(checkbox);
    expect(checkbox).toBeChecked();
    expect(queryComparisonRegion()).not.toBeInTheDocument();
  });

  it('loads the comparison once per candidate and caches it across section changes', async () => {
    const user = userEvent.setup();
    mockComparisonDetail();
    renderPage('/tickets/tkt_123?section=duplicates');

    await user.click(await screen.findByRole('button', { name: 'Compare BG-2026-0201' }));
    expect(
      await (await findComparisonRegion()).findByText('Second report about the same pothole.'),
    ).toBeInTheDocument();
    expect(fetchTicketById).toHaveBeenCalledTimes(2);

    await user.click(screen.getByRole('button', { name: 'Hide comparison for BG-2026-0201' }));
    await user.click(screen.getByRole('button', { name: 'Compare BG-2026-0201' }));
    expect(
      (await findComparisonRegion()).getByText('Second report about the same pothole.'),
    ).toBeInTheDocument();
    expect(fetchTicketById).toHaveBeenCalledTimes(2);

    await openSection(user, 'Activity');
    await openSection(user, /^Duplicates/);
    expect(
      (await findComparisonRegion()).getByText('Second report about the same pothole.'),
    ).toBeInTheDocument();
    expect(fetchTicketById).toHaveBeenCalledTimes(2);
  });

  it('preserves selections while comparisons are opened and closed', async () => {
    const user = userEvent.setup();
    mockComparisonDetail();
    renderPage('/tickets/tkt_123?section=duplicates');

    const checkbox = await screen.findByRole('checkbox', {
      name: 'Select BG-2026-0201 as a duplicate',
    });
    await user.click(checkbox);
    await user.click(screen.getByRole('button', { name: 'Compare BG-2026-0201' }));
    expect(
      await (await findComparisonRegion()).findByText('Second report about the same pothole.'),
    ).toBeInTheDocument();
    expect(checkbox).toBeChecked();

    await user.click(screen.getByRole('button', { name: 'Hide comparison for BG-2026-0201' }));
    expect(
      screen.getByRole('checkbox', { name: 'Select BG-2026-0201 as a duplicate' }),
    ).toBeChecked();
  });

  it('excludes contact details, tracking codes, and raw storage keys from the comparison', async () => {
    const user = userEvent.setup();
    mockComparisonDetail();
    renderPage('/tickets/tkt_123?section=duplicates');

    await user.click(await screen.findByRole('button', { name: 'Compare BG-2026-0201' }));
    expect(
      await (await findComparisonRegion()).findByText('Second report about the same pothole.'),
    ).toBeInTheDocument();

    expect(screen.queryByText('XYZ789')).not.toBeInTheDocument();
    expect(screen.queryByText('Citizen Name')).not.toBeInTheDocument();
    expect(screen.queryByText('+96170000000')).not.toBeInTheDocument();
    expect(screen.queryByText('reports/tkt_same_category.jpg')).not.toBeInTheDocument();
  });

  it('handles a failed comparison locally and retries without reloading the ticket', async () => {
    const user = userEvent.setup();
    vi.mocked(fetchTickets).mockResolvedValue([comparisonCandidate]);
    vi.mocked(fetchTicketById).mockImplementation(async (requestedId: string) => {
      if (requestedId === ticket.ticketId) {
        return ticket;
      }
      throw new Error('Comparison service unavailable.');
    });
    renderPage('/tickets/tkt_123?section=duplicates');

    await user.click(await screen.findByRole('button', { name: 'Compare BG-2026-0201' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Comparison service unavailable.');
    expect(screen.getByText('BG-2026-0201')).toBeInTheDocument();

    mockComparisonDetail();
    await user.click(screen.getByRole('button', { name: 'Retry comparison' }));

    expect(
      await (await findComparisonRegion()).findByText('Second report about the same pothole.'),
    ).toBeInTheDocument();
  });

  it('drops cached comparisons when staff refresh the ticket', async () => {
    const user = userEvent.setup();
    mockComparisonDetail();
    renderPage('/tickets/tkt_123?section=duplicates');

    await user.click(await screen.findByRole('button', { name: 'Compare BG-2026-0201' }));
    expect(
      await (await findComparisonRegion()).findByText('Second report about the same pothole.'),
    ).toBeInTheDocument();
    expect(fetchTicketById).toHaveBeenCalledTimes(2);

    await user.click(screen.getByRole('button', { name: 'Refresh' }));
    await waitFor(() => expect(queryComparisonRegion()).not.toBeInTheDocument());

    await user.click(await screen.findByRole('button', { name: 'Compare BG-2026-0201' }));
    expect(
      await (await findComparisonRegion()).findByText('Second report about the same pothole.'),
    ).toBeInTheDocument();
    expect(fetchTicketById).toHaveBeenCalledTimes(4);
  });
});

describe('TicketDetailPage duplicate merge', () => {
  it('requires confirmation naming the canonical ticket before merging', async () => {
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
    renderPage('/tickets/tkt_123?section=duplicates');

    await user.click(
      await screen.findByRole('checkbox', { name: 'Select BG-2026-0201 as a duplicate' }),
    );
    await user.click(screen.getByRole('button', { name: 'Merge selected as duplicates' }));

    const dialog = await screen.findByRole('dialog');
    expect(
      within(dialog).getByText(/BG-2026-0001 stays the main \(canonical\) ticket/),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText('BG-2026-0201 becomes a duplicate of BG-2026-0001'),
    ).toBeInTheDocument();
    expect(mergeDuplicateTickets).not.toHaveBeenCalled();

    await user.click(within(dialog).getByRole('button', { name: 'Confirm merge' }));

    expect(mergeDuplicateTickets).toHaveBeenCalledWith({
      canonicalTicketId: ticket.ticketId,
      duplicateTicketIds: [candidate.ticketId],
    });
    expect(await screen.findByText(/grouped as the main report/)).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('cancels the merge without applying the mutation', async () => {
    const user = userEvent.setup();
    vi.mocked(fetchTickets).mockResolvedValue([
      buildCandidate({
        ticketId: 'tkt_same_category',
        ticketNumber: 'BG-2026-0201',
        ai: { aiSuggestedCategory: 'road_damage' },
      }),
    ]);
    renderPage('/tickets/tkt_123?section=duplicates');

    await user.click(
      await screen.findByRole('checkbox', { name: 'Select BG-2026-0201 as a duplicate' }),
    );
    await user.click(screen.getByRole('button', { name: 'Merge selected as duplicates' }));
    await user.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'Cancel' }),
    );

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(mergeDuplicateTickets).not.toHaveBeenCalled();
  });

  it('disables merging until a valid candidate is selected', async () => {
    const user = userEvent.setup();
    vi.mocked(fetchTickets).mockResolvedValue([
      buildCandidate({
        ticketId: 'tkt_same_category',
        ticketNumber: 'BG-2026-0201',
        ai: { aiSuggestedCategory: 'road_damage' },
      }),
    ]);
    renderPage('/tickets/tkt_123?section=duplicates');

    const mergeButton = await screen.findByRole('button', {
      name: 'Merge selected as duplicates',
    });
    expect(mergeButton).toBeDisabled();

    await user.click(screen.getByRole('checkbox', { name: 'Select BG-2026-0201 as a duplicate' }));
    expect(mergeButton).toBeEnabled();
  });

  it('summarises the selection when more than one candidate is chosen', async () => {
    const user = userEvent.setup();
    vi.mocked(fetchTickets).mockResolvedValue([
      buildCandidate({
        ticketId: 'tkt_first',
        ticketNumber: 'BG-2026-0201',
        ai: { aiSuggestedCategory: 'road_damage' },
      }),
      buildCandidate({
        ticketId: 'tkt_second',
        ticketNumber: 'BG-2026-0202',
        ai: { aiSuggestedCategory: 'road_damage' },
      }),
    ]);
    renderPage('/tickets/tkt_123?section=duplicates');

    await user.click(
      await screen.findByRole('checkbox', { name: 'Select BG-2026-0201 as a duplicate' }),
    );
    expect(screen.queryByText(/Compare selected/)).not.toBeInTheDocument();

    await user.click(screen.getByRole('checkbox', { name: 'Select BG-2026-0202 as a duplicate' }));
    expect(screen.getByText('Compare selected (2)')).toBeInTheDocument();
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
    renderPage('/tickets/tkt_123?section=duplicates');

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
    renderPage('/tickets/tkt_123?section=duplicates');

    expect(await screen.findByText(/This ticket is grouped/)).toBeInTheDocument();
    expect(screen.getByText('Add further duplicates from the main ticket.')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Merge selected as duplicates' }),
    ).not.toBeInTheDocument();
  });

  it('surfaces merge failures without discarding the ticket', async () => {
    const user = userEvent.setup();
    vi.mocked(fetchTickets).mockResolvedValue([
      buildCandidate({
        ticketId: 'tkt_same_category',
        ticketNumber: 'BG-2026-0201',
        ai: { aiSuggestedCategory: 'road_damage' },
      }),
    ]);
    vi.mocked(mergeDuplicateTickets).mockRejectedValue(
      new Error('Unable to merge duplicate tickets.'),
    );
    renderPage('/tickets/tkt_123?section=duplicates');

    await user.click(
      await screen.findByRole('checkbox', { name: 'Select BG-2026-0201 as a duplicate' }),
    );
    await user.click(screen.getByRole('button', { name: 'Merge selected as duplicates' }));
    await user.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'Confirm merge' }),
    );

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to merge duplicate tickets.',
    );
    expect(screen.getByText('BG-2026-0201')).toBeInTheDocument();
  });
});

describe('TicketDetailPage activity', () => {
  it('merges submission, status history, and audit events into one timeline', async () => {
    vi.mocked(fetchTicketById).mockResolvedValue({
      ...ticket,
      statusHistory: [
        { status: 'SUBMITTED', changedAt: '2026-07-17T08:00:00Z' },
        { status: 'UNDER_REVIEW', changedAt: '2026-07-17T09:00:00Z', changedBy: 'staff-1' },
      ],
      auditHistory: [
        {
          actionType: 'STATUS_CHANGE',
          summary: 'Status changed to UNDER_REVIEW',
          changedAt: '2026-07-17T09:00:00Z',
        },
        {
          actionType: 'DEPARTMENT_ASSIGN',
          summary: 'Assigned to Road Maintenance',
          changedAt: '2026-07-17T10:00:00Z',
          actorId: 'staff-1',
          previousValue: 'Unassigned',
          newValue: 'Road Maintenance',
        },
      ],
    });
    renderPage('/tickets/tkt_123?section=activity');

    const timeline = await screen.findByRole('list', { name: 'Ticket activity timeline' });
    const items = within(timeline).getAllByRole('listitem');

    expect(items).toHaveLength(4);
    expect(items[0]).toHaveTextContent('Department assignment');
    expect(items[0]).toHaveTextContent('Unassigned → Road Maintenance');
    expect(items[1]).toHaveTextContent('Status set to Under Review');
    expect(items[3]).toHaveTextContent('Report submitted by citizen');
    // The audit twin of a status transition is not repeated.
    expect(screen.queryByText('Status changed to UNDER_REVIEW')).not.toBeInTheDocument();
  });

  it('reports partial history without blocking the rest of the ticket', async () => {
    renderPage('/tickets/tkt_123?section=activity');

    expect(
      await screen.findByText(/Status history is unavailable for this ticket/),
    ).toBeInTheDocument();
    expect(screen.getByText('Report submitted by citizen')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'BG-2026-0001' })).toBeInTheDocument();
  });
});

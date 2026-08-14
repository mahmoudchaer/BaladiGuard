import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes, useNavigate } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  assignTicketDepartment,
  createTicketComment,
  fetchTicketActivity,
  fetchTicketComments,
  reviewTicketCategory,
  fetchDuplicateCandidates,
  fetchDuplicateComparison,
  fetchTicketById,
  mergeDuplicateTickets,
  fetchImageRedactionReview,
} from '@/services/tickets';
import { renderWithProviders } from '@/test/render';
import type {
  DuplicateCandidate,
  DuplicateCandidatePage,
  DuplicateComparison,
  Ticket,
} from '@/types/ticket';
import { TicketDetailPage } from '@/pages/TicketDetailPage';

vi.mock('@/services/tickets', () => ({
  fetchTicketById: vi.fn(),
  fetchDuplicateCandidates: vi.fn(),
  fetchDuplicateComparison: vi.fn(),
  mergeDuplicateTickets: vi.fn(),
  reviewTicketCategory: vi.fn(),
  updateTicketStatus: vi.fn(),
  assignTicketDepartment: vi.fn(),
  createTicketComment: vi.fn(),
  fetchTicketActivity: vi.fn(),
  fetchTicketComments: vi.fn(),
  fetchImageRedactionReview: vi.fn(),
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

function TicketNavigationHarness() {
  const navigate = useNavigate();
  return (
    <>
      <button type="button" onClick={() => navigate('/tickets/tkt_456?section=activity')}>
        Open second ticket
      </button>
      <Routes>
        <Route path="/tickets/:ticketId" element={<TicketDetailPage />} />
      </Routes>
    </>
  );
}

async function openSection(user: TestUser, name: RegExp | string) {
  await user.click(await screen.findByRole('tab', { name }));
}

/**
 * Candidates arrive from `GET /v1/tickets/{id}/duplicate-candidates`, which only
 * returns mergeable rows, so fixtures mirror that bounded shape.
 */
function buildCandidate(overrides: Partial<DuplicateCandidate> = {}): DuplicateCandidate {
  return {
    ticketId: 'tkt_same_category',
    ticketNumber: 'BG-2026-0201',
    status: 'SUBMITTED',
    category: 'road_damage',
    priority: null,
    summary: 'Second report about the same pothole.',
    createdAt: '2026-07-17T07:30:00Z',
    location: {
      latitude: 33.8965,
      longitude: 35.4782,
      addressText: 'Bliss Street, Beirut',
    },
    distanceMeters: 42.4,
    suggested: false,
    mergeable: true,
    ...overrides,
  };
}

function candidatePage(
  items: DuplicateCandidate[],
  nextCursor: string | null = null,
): DuplicateCandidatePage {
  return { items, nextCursor, limit: 20 };
}

function buildComparison(overrides: Partial<DuplicateComparison> = {}): DuplicateComparison {
  return {
    ticketId: 'tkt_same_category',
    ticketNumber: 'BG-2026-0201',
    description: 'Second report about the same pothole.',
    status: 'SUBMITTED',
    category: 'road_damage',
    priority: null,
    createdAt: '2026-07-17T07:30:00Z',
    location: {
      latitude: 33.8965,
      longitude: 35.4782,
      addressText: 'Bliss Street, Beirut',
    },
    distanceMeters: 42.4,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchTicketById).mockResolvedValue(ticket);
  vi.mocked(fetchDuplicateCandidates).mockResolvedValue(candidatePage([]));
  vi.mocked(fetchDuplicateComparison).mockResolvedValue(buildComparison());
  vi.mocked(fetchTicketActivity).mockResolvedValue({ events: [], nextCursor: null });
  vi.mocked(fetchTicketComments).mockResolvedValue([]);
  vi.mocked(fetchImageRedactionReview).mockResolvedValue(null);
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
    expect(fetchDuplicateCandidates).toHaveBeenCalledTimes(1);
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
    vi.mocked(fetchDuplicateCandidates).mockResolvedValue(
      candidatePage([
        buildCandidate({
          ticketId: 'tkt_duplicate',
          ticketNumber: 'BG-2026-0201',
          status: 'IN_PROGRESS',
          category: 'waste',
          distanceMeters: 42.4,
          suggested: true,
        }),
      ]),
    );
    renderPage('/tickets/tkt_123?section=duplicates');

    expect(await screen.findByText('Possible duplicates')).toBeInTheDocument();
    expect(await screen.findByRole('link', { name: 'BG-2026-0201' })).toHaveAttribute(
      'href',
      '/tickets/tkt_duplicate',
    );
    expect(screen.getByText('42 m away')).toBeInTheDocument();
    expect(screen.getByText('In Progress')).toBeInTheDocument();
    expect(screen.getAllByText('Waste').length).toBeGreaterThan(0);
    expect(screen.getByText('Suggested match')).toBeInTheDocument();
  });

  it('loads candidates from the dedicated endpoint for this ticket only', async () => {
    vi.mocked(fetchDuplicateCandidates).mockResolvedValue(
      candidatePage([buildCandidate({ ticketNumber: 'BG-2026-0201' })]),
    );
    renderPage('/tickets/tkt_123?section=duplicates');

    expect(await screen.findByText('BG-2026-0201')).toBeInTheDocument();
    expect(fetchDuplicateCandidates).toHaveBeenCalledWith(
      'tkt_123',
      expect.objectContaining({ q: undefined }),
    );
  });

  it('sends the candidate search to the backend instead of filtering one page', async () => {
    const user = userEvent.setup();
    vi.mocked(fetchDuplicateCandidates).mockResolvedValue(
      candidatePage([buildCandidate({ ticketNumber: 'BG-2026-0201' })]),
    );
    renderPage('/tickets/tkt_123?section=duplicates');

    await user.type(
      await screen.findByRole('searchbox', { name: 'Search duplicate candidates' }),
      'bliss',
    );

    await waitFor(() =>
      expect(fetchDuplicateCandidates).toHaveBeenLastCalledWith(
        'tkt_123',
        expect.objectContaining({ q: 'bliss' }),
      ),
    );
  });

  it('reaches a candidate beyond the first page through the continuation cursor', async () => {
    const user = userEvent.setup();
    vi.mocked(fetchDuplicateCandidates).mockImplementation(async (_ticketId, options) =>
      options?.cursor === 'cursor-2'
        ? candidatePage([
            buildCandidate({ ticketId: 'tkt_page_two', ticketNumber: 'BG-2026-0399' }),
          ])
        : candidatePage([buildCandidate({ ticketNumber: 'BG-2026-0201' })], 'cursor-2'),
    );
    renderPage('/tickets/tkt_123?section=duplicates');

    expect(await screen.findByText('BG-2026-0201')).toBeInTheDocument();
    expect(screen.queryByText('BG-2026-0399')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Load more candidates' }));

    expect(await screen.findByText('BG-2026-0399')).toBeInTheDocument();
    expect(screen.getByText('BG-2026-0201')).toBeInTheDocument();
    expect(
      screen.getByRole('checkbox', { name: 'Select BG-2026-0399 as a duplicate' }),
    ).toBeInTheDocument();
  });

  it('reports a failed candidate search without discarding the ticket', async () => {
    vi.mocked(fetchDuplicateCandidates).mockRejectedValue(
      new Error('Unable to load duplicate candidates.'),
    );
    renderPage('/tickets/tkt_123?section=duplicates');

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to load duplicate candidates.',
    );
    expect(screen.getByRole('button', { name: 'Retry candidate search' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'BG-2026-0001' })).toBeInTheDocument();
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
    expect(fetchDuplicateCandidates).not.toHaveBeenCalled();
    expect(
      screen.queryByRole('button', { name: 'Merge selected as duplicates' }),
    ).not.toBeInTheDocument();
  });

  it('offers every returned candidate as mergeable', async () => {
    vi.mocked(fetchDuplicateCandidates).mockResolvedValue(
      candidatePage([
        buildCandidate({ ticketId: 'tkt_first', ticketNumber: 'BG-2026-0201' }),
        buildCandidate({ ticketId: 'tkt_second', ticketNumber: 'BG-2026-0202' }),
      ]),
    );
    renderPage('/tickets/tkt_123?section=duplicates');

    expect(await screen.findByText('BG-2026-0201')).toBeInTheDocument();
    expect(screen.getByText('BG-2026-0202')).toBeInTheDocument();
    expect(screen.queryByText('Not available to merge')).not.toBeInTheDocument();
    expect(
      screen.getByRole('checkbox', { name: 'Select BG-2026-0201 as a duplicate' }),
    ).toBeEnabled();
  });

  it('gives each candidate enough context to make a responsible decision', async () => {
    vi.mocked(fetchDuplicateCandidates).mockResolvedValue(
      candidatePage([
        buildCandidate({
          ticketNumber: 'BG-2026-0201',
          summary: 'Deep pothole opposite the campus entrance.',
          priority: 'high',
        }),
      ]),
    );
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

const comparisonCandidate = buildCandidate();

function mockComparisonDetail(candidate: DuplicateCandidate = comparisonCandidate) {
  vi.mocked(fetchTicketById).mockResolvedValue(ticket);
  vi.mocked(fetchDuplicateCandidates).mockResolvedValue(candidatePage([candidate]));
  vi.mocked(fetchDuplicateComparison).mockResolvedValue(
    buildComparison({
      ticketId: candidate.ticketId,
      ticketNumber: candidate.ticketNumber,
      description: candidate.summary,
      status: candidate.status,
      category: candidate.category,
      priority: candidate.priority,
      createdAt: candidate.createdAt,
      location: candidate.location,
      distanceMeters: candidate.distanceMeters,
    }),
  );
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
    expect(fetchDuplicateComparison).toHaveBeenCalledTimes(1);
    expect(fetchDuplicateComparison).toHaveBeenCalledWith('tkt_123', 'tkt_same_category');
    expect(fetchTicketById).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole('button', { name: 'Hide comparison for BG-2026-0201' }));
    await user.click(screen.getByRole('button', { name: 'Compare BG-2026-0201' }));
    expect(
      (await findComparisonRegion()).getByText('Second report about the same pothole.'),
    ).toBeInTheDocument();
    expect(fetchDuplicateComparison).toHaveBeenCalledTimes(1);

    await openSection(user, 'Activity');
    await openSection(user, /^Duplicates/);
    expect(
      (await findComparisonRegion()).getByText('Second report about the same pothole.'),
    ).toBeInTheDocument();
    expect(fetchDuplicateComparison).toHaveBeenCalledTimes(1);
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

  it('never requests the full candidate ticket for a comparison', async () => {
    const user = userEvent.setup();
    mockComparisonDetail();
    renderPage('/tickets/tkt_123?section=duplicates');

    await user.click(await screen.findByRole('button', { name: 'Compare BG-2026-0201' }));
    expect(
      await (await findComparisonRegion()).findByText('Second report about the same pothole.'),
    ).toBeInTheDocument();

    // The bounded projection is the only candidate read, so contact details,
    // tracking codes, and storage keys never reach the browser at all.
    expect(fetchDuplicateComparison).toHaveBeenCalledWith('tkt_123', 'tkt_same_category');
    expect(vi.mocked(fetchTicketById).mock.calls).toEqual([['tkt_123']]);
    expect(screen.queryByText('XYZ789')).not.toBeInTheDocument();
    expect(screen.queryByText('Citizen Name')).not.toBeInTheDocument();
    expect(screen.queryByText('+96170000000')).not.toBeInTheDocument();
    expect(screen.queryByText('reports/tkt_same_category.jpg')).not.toBeInTheDocument();
  });

  it('handles a failed comparison locally and retries without reloading the ticket', async () => {
    const user = userEvent.setup();
    vi.mocked(fetchDuplicateCandidates).mockResolvedValue(candidatePage([comparisonCandidate]));
    vi.mocked(fetchDuplicateComparison).mockRejectedValue(
      new Error('Comparison service unavailable.'),
    );
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
    expect(fetchDuplicateComparison).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole('button', { name: 'Refresh' }));
    await waitFor(() => expect(queryComparisonRegion()).not.toBeInTheDocument());

    await user.click(await screen.findByRole('button', { name: 'Compare BG-2026-0201' }));
    expect(
      await (await findComparisonRegion()).findByText('Second report about the same pothole.'),
    ).toBeInTheDocument();
    expect(fetchTicketById).toHaveBeenCalledTimes(2);
    expect(fetchDuplicateComparison).toHaveBeenCalledTimes(2);
  });
});

/**
 * Selecting a candidate starts its comparison fetch; merging only unlocks once
 * that comparison is ready, so tests wait for the gate to open.
 */
async function selectCandidate(user: TestUser, ticketNumber: string) {
  await user.click(
    await screen.findByRole('checkbox', { name: `Select ${ticketNumber} as a duplicate` }),
  );
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Merge selected as duplicates' })).toBeEnabled(),
  );
}

describe('TicketDetailPage duplicate merge', () => {
  it('requires confirmation naming the canonical ticket before merging', async () => {
    const user = userEvent.setup();
    const candidate = buildCandidate();
    mockComparisonDetail(candidate);
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

    await selectCandidate(user, 'BG-2026-0201');
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
    mockComparisonDetail();
    renderPage('/tickets/tkt_123?section=duplicates');

    await selectCandidate(user, 'BG-2026-0201');
    await user.click(screen.getByRole('button', { name: 'Merge selected as duplicates' }));
    await user.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'Cancel' }),
    );

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(mergeDuplicateTickets).not.toHaveBeenCalled();
  });

  it('disables merging until a valid candidate is selected', async () => {
    const user = userEvent.setup();
    mockComparisonDetail();
    renderPage('/tickets/tkt_123?section=duplicates');

    const mergeButton = await screen.findByRole('button', {
      name: 'Merge selected as duplicates',
    });
    expect(mergeButton).toBeDisabled();

    await selectCandidate(user, 'BG-2026-0201');
    expect(mergeButton).toBeEnabled();
  });

  it('summarises the selection when more than one candidate is chosen', async () => {
    const user = userEvent.setup();
    vi.mocked(fetchDuplicateCandidates).mockResolvedValue(
      candidatePage([
        buildCandidate({ ticketId: 'tkt_first', ticketNumber: 'BG-2026-0201' }),
        buildCandidate({ ticketId: 'tkt_second', ticketNumber: 'BG-2026-0202' }),
      ]),
    );
    vi.mocked(fetchDuplicateComparison).mockImplementation(async (_sourceId, candidateId) =>
      buildComparison({
        ticketId: candidateId,
        ticketNumber: candidateId === 'tkt_first' ? 'BG-2026-0201' : 'BG-2026-0202',
      }),
    );
    renderPage('/tickets/tkt_123?section=duplicates');

    await selectCandidate(user, 'BG-2026-0201');
    expect(screen.queryByText(/Compare selected/)).not.toBeInTheDocument();

    await selectCandidate(user, 'BG-2026-0202');
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
    mockComparisonDetail();
    vi.mocked(mergeDuplicateTickets).mockRejectedValue(
      new Error('Unable to merge duplicate tickets.'),
    );
    renderPage('/tickets/tkt_123?section=duplicates');

    await selectCandidate(user, 'BG-2026-0201');
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

describe('TicketDetailPage merge gate', () => {
  it('starts the comparison as soon as a candidate is selected', async () => {
    const user = userEvent.setup();
    mockComparisonDetail();
    renderPage('/tickets/tkt_123?section=duplicates');

    await user.click(
      await screen.findByRole('checkbox', { name: 'Select BG-2026-0201 as a duplicate' }),
    );

    await waitFor(() =>
      expect(fetchDuplicateComparison).toHaveBeenCalledWith('tkt_123', 'tkt_same_category'),
    );
  });

  it('keeps merging disabled while a selected comparison is still loading', async () => {
    const user = userEvent.setup();
    vi.mocked(fetchDuplicateCandidates).mockResolvedValue(candidatePage([buildCandidate()]));
    vi.mocked(fetchDuplicateComparison).mockReturnValue(new Promise(() => undefined));
    renderPage('/tickets/tkt_123?section=duplicates');

    await user.click(
      await screen.findByRole('checkbox', { name: 'Select BG-2026-0201 as a duplicate' }),
    );

    expect(screen.getByRole('button', { name: 'Merge selected as duplicates' })).toBeDisabled();
    expect(
      screen.getByText(/Merging unlocks once every comparison is ready to review/),
    ).toBeInTheDocument();
  });

  it('does not open the confirm dialog while a selected comparison is unresolved', async () => {
    const user = userEvent.setup();
    vi.mocked(fetchDuplicateCandidates).mockResolvedValue(candidatePage([buildCandidate()]));
    vi.mocked(fetchDuplicateComparison).mockReturnValue(new Promise(() => undefined));
    renderPage('/tickets/tkt_123?section=duplicates');

    await user.click(
      await screen.findByRole('checkbox', { name: 'Select BG-2026-0201 as a duplicate' }),
    );
    await user.click(screen.getByRole('button', { name: 'Merge selected as duplicates' }));

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(mergeDuplicateTickets).not.toHaveBeenCalled();
  });

  it('keeps merging disabled when a selected comparison failed and offers a retry', async () => {
    const user = userEvent.setup();
    vi.mocked(fetchDuplicateCandidates).mockResolvedValue(candidatePage([buildCandidate()]));
    vi.mocked(fetchDuplicateComparison).mockRejectedValue(
      new Error('Comparison service unavailable.'),
    );
    renderPage('/tickets/tkt_123?section=duplicates');

    await user.click(
      await screen.findByRole('checkbox', { name: 'Select BG-2026-0201 as a duplicate' }),
    );

    expect(
      await screen.findByText(/A comparison could not be loaded for 1 selected ticket/),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Merge selected as duplicates' })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'Compare BG-2026-0201' }));
    expect(screen.getByRole('button', { name: 'Retry comparison' })).toBeInTheDocument();

    vi.mocked(fetchDuplicateComparison).mockResolvedValue(buildComparison());
    await user.click(screen.getByRole('button', { name: 'Retry comparison' }));

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Merge selected as duplicates' })).toBeEnabled(),
    );
  });

  it('enables merging only once every selected comparison is ready', async () => {
    const user = userEvent.setup();
    let resolveSecond: ((comparison: DuplicateComparison) => void) | undefined;
    vi.mocked(fetchDuplicateCandidates).mockResolvedValue(
      candidatePage([
        buildCandidate({ ticketId: 'tkt_first', ticketNumber: 'BG-2026-0201' }),
        buildCandidate({ ticketId: 'tkt_second', ticketNumber: 'BG-2026-0202' }),
      ]),
    );
    vi.mocked(fetchDuplicateComparison).mockImplementation(async (_sourceId, candidateId) => {
      if (candidateId === 'tkt_first') {
        return buildComparison({ ticketId: 'tkt_first', ticketNumber: 'BG-2026-0201' });
      }
      return new Promise<DuplicateComparison>((resolve) => {
        resolveSecond = resolve;
      });
    });
    renderPage('/tickets/tkt_123?section=duplicates');

    await selectCandidate(user, 'BG-2026-0201');

    await user.click(screen.getByRole('checkbox', { name: 'Select BG-2026-0202 as a duplicate' }));
    const mergeButton = screen.getByRole('button', { name: 'Merge selected as duplicates' });
    expect(mergeButton).toBeDisabled();

    resolveSecond?.(buildComparison({ ticketId: 'tkt_second', ticketNumber: 'BG-2026-0202' }));

    await waitFor(() => expect(mergeButton).toBeEnabled());
    expect(
      screen.queryByText(/Merging unlocks once every comparison is ready to review/),
    ).not.toBeInTheDocument();
  });
});

describe('TicketDetailPage activity', () => {
  it('renders normalized events and private comments once in chronological order', async () => {
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
    vi.mocked(fetchTicketActivity).mockResolvedValue({
      events: [
        {
          eventId: 'status:1',
          eventType: 'STATUS_CHANGED',
          occurredAt: '2026-07-17T08:00:00Z',
          actorDisplayName: 'Administrator',
          details: { status: 'UNDER_REVIEW' },
          sourceReference: 'status-history:1',
        },
        {
          eventId: 'comment:cmt_1',
          eventType: 'STAFF_COMMENT',
          occurredAt: '2026-07-17T08:30:00Z',
          actorDisplayName: 'Roads operator',
          details: { commentId: 'cmt_1' },
          sourceReference: 'comment:cmt_1',
        },
        {
          eventId: 'audit:1',
          eventType: 'CATEGORY_REVIEW',
          occurredAt: '2026-07-17T09:00:00Z',
          actorDisplayName: 'Administrator',
          details: { summary: 'Category confirmed.' },
          sourceReference: 'audit:1',
        },
      ],
      nextCursor: null,
    });
    vi.mocked(fetchTicketComments).mockResolvedValue([
      {
        commentId: 'cmt_1',
        ticketId: ticket.ticketId,
        authorStaffId: 'staff_roads_1',
        authorDisplayName: 'Roads operator',
        text: 'Inspection is scheduled for this afternoon.',
        mentionedStaffIds: ['staff_admin_001'],
        createdAt: '2026-07-17T08:30:00Z',
      },
    ]);
    renderPage('/tickets/tkt_123?section=activity');

    const timeline = await screen.findByRole('list', { name: 'Internal ticket activity' });
    const items = within(timeline).getAllByRole('listitem');

    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent('STATUS CHANGED');
    expect(items[1]).toHaveTextContent('Internal comment');
    expect(items[1]).toHaveTextContent('Inspection is scheduled for this afternoon.');
    expect(items[1]).toHaveTextContent('Mentioned: staff_admin_001');
    expect(items[2]).toHaveTextContent('CATEGORY REVIEW');
    expect(within(timeline).getAllByText('CATEGORY REVIEW')).toHaveLength(1);
    expect(screen.queryByRole('heading', { name: 'Operational timeline' })).not.toBeInTheDocument();
  });

  it('keeps comments visible and retryable when normalized activity fails', async () => {
    vi.mocked(fetchTicketActivity).mockRejectedValue(new Error('Activity unavailable.'));
    vi.mocked(fetchTicketComments).mockResolvedValue([
      {
        commentId: 'cmt_partial',
        ticketId: ticket.ticketId,
        authorStaffId: 'staff_admin_001',
        authorDisplayName: 'Administrator',
        text: 'This comment remains available.',
        mentionedStaffIds: [],
        createdAt: '2026-07-17T08:05:00Z',
      },
    ]);
    renderPage('/tickets/tkt_123?section=activity');

    expect(await screen.findByText('This comment remains available.')).toBeInTheDocument();
    expect(screen.getByText('Activity unavailable.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry activity' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'BG-2026-0001' })).toBeInTheDocument();
  });

  it('keeps a posted comment when the activity refresh fails', async () => {
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
    renderPage('/tickets/tkt_123?section=activity');

    await user.type(
      await screen.findByLabelText('Add internal comment'),
      'Please inspect the road closure.',
    );
    await user.click(screen.getByRole('button', { name: 'Post comment' }));

    expect(await screen.findByText('Please inspect the road closure.')).toBeInTheDocument();
    expect(await screen.findByText('Activity refresh failed.')).toBeInTheDocument();
    expect(screen.queryByText('Unable to add comment.')).not.toBeInTheDocument();
  });

  it('ignores a comment post that completes after navigating to another ticket', async () => {
    const user = userEvent.setup();
    let resolveComment:
      ((comment: Awaited<ReturnType<typeof createTicketComment>>) => void) | null = null;
    vi.mocked(createTicketComment).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveComment = resolve;
        }),
    );
    vi.mocked(fetchTicketById).mockImplementation(async (id) => ({
      ...ticket,
      ticketId: id,
      ticketNumber: id === 'tkt_456' ? 'BG-2026-0002' : ticket.ticketNumber,
    }));
    renderWithProviders(<TicketNavigationHarness />, {
      route: '/tickets/tkt_123?section=activity',
    });

    await user.type(
      await screen.findByLabelText('Add internal comment'),
      'Comment for the first ticket',
    );
    await user.click(screen.getByRole('button', { name: 'Post comment' }));
    expect(screen.getByRole('button', { name: 'Posting…' })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'Open second ticket' }));
    await waitFor(() => expect(fetchTicketById).toHaveBeenCalledWith('tkt_456'));
    await waitFor(() => expect(screen.getByLabelText('Add internal comment')).toHaveValue(''));

    await act(async () => {
      resolveComment?.({
        commentId: 'cmt_first_ticket',
        ticketId: 'tkt_123',
        authorStaffId: 'staff_admin_001',
        authorDisplayName: 'Administrator',
        text: 'Comment for the first ticket',
        mentionedStaffIds: [],
        createdAt: '2026-07-17T08:05:00Z',
      });
    });

    expect(screen.queryByText('Comment for the first ticket')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Post comment' })).toBeDisabled();
  });
});

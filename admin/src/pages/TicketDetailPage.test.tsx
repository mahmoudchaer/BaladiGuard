import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
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
  departmentId: null,
  duplicateGroupId: null,
  createdAt: '2026-07-17T08:00:00Z',
  updatedAt: '2026-07-17T08:01:00Z',
  ai: {
    originalDescription: 'Large pothole near the university gate.',
    aiSuggestedCategory: 'road_damage',
    aiCategoryExplanation: 'The report describes damage to a public road.',
    aiConfidence: 0.92,
    aiProcessingStatus: 'completed',
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
});

describe('TicketDetailPage category review', () => {
  it('shows the stored AI suggestion and explanation', async () => {
    renderPage();

    expect(await screen.findByText('AI category recommendation')).toBeInTheDocument();
    expect(screen.getByText('The report describes damage to a public road.')).toBeInTheDocument();
    expect(screen.getByText('Confidence 92%')).toBeInTheDocument();
    expect(screen.getByText('62/100')).toBeInTheDocument();
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

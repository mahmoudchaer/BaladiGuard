import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { reviewTicketCategory, fetchTicketById } from '@/services/tickets';
import { renderWithProviders } from '@/test/render';
import type { Ticket } from '@/types/ticket';
import { TicketDetailPage } from '@/pages/TicketDetailPage';

vi.mock('@/services/tickets', () => ({
  fetchTicketById: vi.fn(),
  reviewTicketCategory: vi.fn(),
  updateTicketStatus: vi.fn(),
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

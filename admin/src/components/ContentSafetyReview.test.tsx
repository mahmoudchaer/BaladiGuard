import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ContentSafetyReviewPanel } from '@/components/ContentSafetyReview';
import { renderWithProviders } from '@/test/render';
import { markContentSafetyPrivate } from '@/services/tickets';

vi.mock('@/services/tickets', async () => {
  const actual = await vi.importActual<typeof import('@/services/tickets')>('@/services/tickets');
  return {
    ...actual,
    fetchContentSafetyReview: vi.fn(async () => ({
      ticketId: 'tkt_1',
      generation: 1,
      status: 'review_required' as const,
      reasonCode: 'TEXT_UNSAFE',
      severity: 'medium' as const,
      imageLabels: ['hate-symbols'],
      authenticityScore: 0.12,
      authenticitySignals: ['AUTH_EXIF_MISSING'],
      originalImageUrl: 'https://example.test/original.jpg',
      publicImageReady: false,
      canApprove: true,
      canReject: true,
      canMarkPrivate: true,
      canReprocess: true,
    })),
    markContentSafetyPrivate: vi.fn(),
  };
});

describe('ContentSafetyReviewPanel', () => {
  it('shows bounded codes without detector internals or storage keys', async () => {
    renderWithProviders(<ContentSafetyReviewPanel ticketId="tkt_1" category="road_damage" />);
    expect(await screen.findByText('Allow public eligibility')).toBeInTheDocument();
    expect(screen.getByText('Keep private only')).toBeInTheDocument();
    expect(screen.getByText('Reject as unsafe')).toBeInTheDocument();
    expect(screen.getByText('Reason: TEXT_UNSAFE')).toBeInTheDocument();
    expect(screen.queryByText(/reports\//)).not.toBeInTheDocument();
  });

  it('does not mark a report private when the confirm is cancelled', async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    renderWithProviders(<ContentSafetyReviewPanel ticketId="tkt_1" category="road_damage" />);
    await user.click(await screen.findByRole('button', { name: 'Keep private only' }));
    expect(confirm).toHaveBeenCalled();
    expect(markContentSafetyPrivate).not.toHaveBeenCalled();
    confirm.mockRestore();
  });
});

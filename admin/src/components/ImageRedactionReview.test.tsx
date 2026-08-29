import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ImageRedactionReviewPanel } from '@/components/ImageRedactionReview';
import { renderWithProviders } from '@/test/render';
import { rejectImageRedaction } from '@/services/tickets';

vi.mock('@/services/tickets', async () => {
  const actual = await vi.importActual<typeof import('@/services/tickets')>('@/services/tickets');
  return {
    ...actual,
    fetchImageRedactionReview: vi.fn(async () => ({
      ticketId: 'tkt_1',
      generation: 1,
      candidateRevision: 1,
      status: 'review_required' as const,
      originalImageUrl: 'https://example.test/original.jpg',
      candidateImageUrl: 'https://example.test/candidate.jpg',
      publicImageReady: false,
      faceCount: 0,
      plateCount: 1,
      reasonCode: 'LOW_CONFIDENCE',
      regions: [],
      canApprove: true,
      canReject: true,
      canReprocess: true,
      canAddManualRegions: true,
    })),
    rejectImageRedaction: vi.fn(),
  };
});

describe('ImageRedactionReviewPanel', () => {
  it('shows original and candidate controls without storage keys', async () => {
    renderWithProviders(<ImageRedactionReviewPanel ticketId="tkt_1" category="road_damage" />);
    expect(await screen.findByText('Approve public derivative')).toBeInTheDocument();
    expect(screen.getByText('Keep private only')).toBeInTheDocument();
    expect(screen.getByText('Original (staff only)')).toBeInTheDocument();
    expect(screen.getByText('Redacted candidate')).toBeInTheDocument();
    expect(screen.queryByText(/reports\//)).not.toBeInTheDocument();
  });

  it('does not reject a public candidate when the confirm is cancelled', async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    renderWithProviders(<ImageRedactionReviewPanel ticketId="tkt_1" category="road_damage" />);
    await user.click(await screen.findByRole('button', { name: 'Keep private only' }));
    expect(confirm).toHaveBeenCalled();
    expect(rejectImageRedaction).not.toHaveBeenCalled();
    confirm.mockRestore();
  });
});

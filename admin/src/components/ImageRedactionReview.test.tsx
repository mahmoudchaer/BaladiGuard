import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ImageRedactionReviewPanel } from '@/components/ImageRedactionReview';
import { renderWithProviders } from '@/test/render';

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
  };
});

describe('ImageRedactionReviewPanel', () => {
  it('reviews original and candidate in one gallery without storage keys', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ImageRedactionReviewPanel ticketId="tkt_1" category="road_damage" />);
    expect(await screen.findByText('Approve public derivative')).toBeInTheDocument();
    expect(screen.getByText('Keep private only')).toBeInTheDocument();
    expect(screen.getByText('Original (staff only)')).toBeInTheDocument();
    expect(screen.getByText('1/2')).toBeInTheDocument();
    expect(screen.queryByText('Redacted candidate')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Show next image' }));
    expect(screen.getByText('Redacted candidate')).toBeInTheDocument();
    expect(screen.getByText('2/2')).toBeInTheDocument();
    expect(screen.queryByText(/reports\//)).not.toBeInTheDocument();
  });
});

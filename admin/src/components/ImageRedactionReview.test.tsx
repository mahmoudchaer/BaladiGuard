import { screen } from '@testing-library/react';
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
  it('shows original and candidate controls without storage keys', async () => {
    renderWithProviders(<ImageRedactionReviewPanel ticketId="tkt_1" category="road_damage" />);
    expect(await screen.findByText('Approve public derivative')).toBeInTheDocument();
    expect(screen.getByText('Keep private only')).toBeInTheDocument();
    expect(screen.getByText('Original (staff only)')).toBeInTheDocument();
    expect(screen.getByText('Redacted candidate')).toBeInTheDocument();
    expect(screen.queryByText(/reports\//)).not.toBeInTheDocument();
  });
});

import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ContentSafetyReviewPanel } from '@/components/ContentSafetyReview';
import { renderWithProviders } from '@/test/render';

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
});

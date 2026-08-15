import React from 'react';
import { act } from 'react-test-renderer';
import { describe, expect, it, vi } from 'vitest';

import { ResolutionFeedbackCard } from '@/components/ResolutionFeedbackCard';
import { renderWithProviders } from '@/test/render';
import type { CitizenResolutionFeedback } from '@/types/ticket';

const prompt: CitizenResolutionFeedback = {
  trackingCode: 'AB23CD',
  ticketStatus: 'RESOLVED',
  canSubmit: true,
  status: null,
  submittedAt: null,
};

describe('ResolutionFeedbackCard', () => {
  it('prompts the owner and retries the same choice', async () => {
    const onSubmit = vi.fn();
    const screen = renderWithProviders(
      <ResolutionFeedbackCard trackingCode="AB23CD" feedback={prompt} onSubmit={onSubmit} />,
    );

    expect(screen.root.findByProps({ testID: 'resolution-feedback-AB23CD' })).toBeTruthy();
    await act(async () => {
      screen.root.findByProps({ testID: 'resolution-feedback-fixed-AB23CD' }).props.onPress();
    });
    expect(onSubmit).toHaveBeenCalledWith('CONFIRMED_FIXED', undefined);
  });

  it('shows the submitted state so the owner can retry', () => {
    const screen = renderWithProviders(
      <ResolutionFeedbackCard
        trackingCode="AB23CD"
        feedback={{ ...prompt, canSubmit: false, status: 'STILL_UNRESOLVED' }}
        onSubmit={vi.fn()}
      />,
    );
    expect(
      screen.root.findByProps({ testID: 'resolution-feedback-submitted-AB23CD' }).props.children,
    ).toMatch(/still unresolved/i);
  });
});

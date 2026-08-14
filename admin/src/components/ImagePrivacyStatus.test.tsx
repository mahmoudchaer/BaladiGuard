import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ImagePrivacyStatus } from '@/components/ImagePrivacyStatus';
import { renderWithProviders } from '@/test/render';

describe('ImagePrivacyStatus', () => {
  it('fails closed when processing state is absent', () => {
    renderWithProviders(<ImagePrivacyStatus />);
    expect(screen.getByRole('status')).toHaveTextContent('Waiting for privacy processing');
  });

  it('shows safe completed counts without exposing storage details', () => {
    renderWithProviders(
      <ImagePrivacyStatus
        redaction={{
          status: 'completed',
          generation: 2,
          faceCount: 3,
          plateCount: 1,
        }}
      />,
    );
    const status = screen.getByRole('status');
    expect(status).toHaveTextContent('Public derivative is privacy-safe');
    expect(status).toHaveTextContent('3 face(s) and 1 plate(s) redacted');
    expect(status).not.toHaveTextContent('reports/');
  });

  it('states that private-only keeps the original unpublished', () => {
    renderWithProviders(
      <ImagePrivacyStatus
        redaction={{ status: 'private_only', generation: 1, faceCount: 0, plateCount: 0 }}
      />,
    );
    expect(screen.getByRole('status')).toHaveTextContent('Private only — no public derivative');
  });
});

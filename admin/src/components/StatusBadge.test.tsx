import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { StatusBadge } from '@/components/StatusBadge';
import { renderWithProviders } from '@/test/render';

describe('StatusBadge', () => {
  it('renders a readable ticket status label', () => {
    renderWithProviders(<StatusBadge status="UNDER_REVIEW" />);

    expect(screen.getByText('Under Review')).toBeInTheDocument();
  });
});

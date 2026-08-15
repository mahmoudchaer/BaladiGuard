import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { installControlledBackend, renderApp } from '@/e2e/harness';

vi.mock('@/components/PublicReportsMap', () => ({
  PublicReportsMap: () => null,
}));

describe('guest browse and tracking E2E', () => {
  beforeEach(() => {
    installControlledBackend(false);
  });

  it('browses the public directory and opens citizen-safe detail', async () => {
    const user = userEvent.setup();
    renderApp('/reports');

    expect(await screen.findByTestId('public-report-list')).toBeInTheDocument();
    expect(screen.getByText('BG-100001')).toBeInTheDocument();
    await user.click(screen.getByRole('link', { name: /BG-100001/i }));
    expect(await screen.findByTestId('public-detail')).toBeInTheDocument();
    expect(screen.queryByText(/ticketId|imageObjectKey/i)).not.toBeInTheDocument();
  });

  it('tracks a report by possession code without signing in', async () => {
    const user = userEvent.setup();
    renderApp('/track');
    await user.type(screen.getByLabelText('Tracking code'), 'ABC234');
    await user.click(screen.getByRole('button', { name: 'Look up' }));
    expect(await screen.findByTestId('track-result')).toBeInTheDocument();
    expect(screen.getByText(/Tracking code: ABC234/)).toBeInTheDocument();
    expect(screen.getAllByText(/IN PROGRESS/i).length).toBeGreaterThan(0);
  });

  it('shows the citizen-safe outcome message and hides private resolution fields', async () => {
    const user = userEvent.setup();
    renderApp('/track');
    await user.type(screen.getByLabelText('Tracking code'), 'RES234');
    await user.click(screen.getByRole('button', { name: 'Look up' }));
    expect(await screen.findByTestId('track-outcome')).toHaveTextContent(
      'The reported issue has been resolved.',
    );
    expect(document.body.textContent).not.toMatch(
      /WORK_COMPLETED|private crew address|Internal close note|secret-ticket-id/,
    );
  });

  it('offers track or sign-in on a notification deep link', async () => {
    renderApp('/t/ABC234');
    expect(await screen.findByTestId('notification-link-guest')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Track with this code' })).toHaveAttribute(
      'href',
      '/track?trackingCode=ABC234',
    );
    expect(screen.getByRole('link', { name: 'Sign in to continue' })).toHaveAttribute(
      'href',
      '/login?returnTo=%2Ft%2FABC234',
    );
    expect(document.body.textContent?.toLowerCase()).not.toContain('not yours');
  });

  it('uses a safe fallback for a malformed notification link', async () => {
    renderApp('/t/!!');
    expect(await screen.findByTestId('notification-link-invalid')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Link cannot be used' })).toBeInTheDocument();
    expect(document.body.textContent?.toLowerCase()).not.toContain('does not belong');
  });

  it('keeps the public map usable with a list alternative', async () => {
    renderApp('/map');
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'View as list' })).toHaveAttribute(
        'href',
        '/reports',
      );
    });
  });
});

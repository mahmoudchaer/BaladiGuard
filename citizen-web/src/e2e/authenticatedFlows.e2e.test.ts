import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { installControlledBackend, renderApp } from '@/e2e/harness';

vi.mock('@/components/PublicReportsMap', () => ({
  PublicReportsMap: () => null,
}));

describe('authenticated OTP, profile, report, history, and logout E2E', () => {
  it('restores a notification deep link after phone OTP', async () => {
    const user = userEvent.setup();
    installControlledBackend(false);
    renderApp('/login?returnTo=/t/ABC234');

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
    await user.type(screen.getByLabelText('Phone number'), '70123456');
    await user.click(screen.getByRole('button', { name: /Continue/ }));
    expect(await screen.findByLabelText('Verification code')).toBeInTheDocument();
    await user.type(screen.getByLabelText('Verification code'), '123456');
    await user.click(screen.getByRole('checkbox', { name: /I agree to the/i }));
    await user.click(screen.getByRole('button', { name: 'Verify and continue' }));

    expect(await screen.findByTestId('track-result')).toBeInTheDocument();
    expect(screen.getByText(/Tracking code: ABC234/)).toBeInTheDocument();
  });

  it('updates the profile, loads history feedback, and signs out', async () => {
    const user = userEvent.setup();
    installControlledBackend(true);
    renderApp('/profile');

    expect(await screen.findByRole('heading', { name: 'Profile' })).toBeInTheDocument();
    const name = screen.getByLabelText(/Full name/);
    await user.clear(name);
    await user.type(name, 'Ada Updated');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByText('Your profile was updated.')).toBeInTheDocument();

    await user.click(screen.getByRole('link', { name: 'My reports' }));
    expect(await screen.findByRole('heading', { name: 'My reports' })).toBeInTheDocument();
    expect(screen.getByText(/Was this issue fixed/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Confirmed fixed' }));
    await waitFor(() => {
      expect(screen.getByText('You confirmed this report was fixed.')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: 'Open profile' }));
    await user.click(await screen.findByRole('button', { name: /Sign out/ }));
    expect(await screen.findByRole('link', { name: 'Sign in' })).toBeInTheDocument();
  });

  it('submits a report when the session is contribution-ready', async () => {
    const user = userEvent.setup();
    installControlledBackend(true);
    renderApp('/report');

    expect(
      await screen.findByRole('heading', { name: 'What needs attention?' }),
    ).toBeInTheDocument();
    await user.type(
      screen.getByLabelText('Describe the issue'),
      'Broken sidewalk blocks the ramp.',
    );
    await user.type(screen.getByLabelText('Location'), 'Hamra');
    await user.click(screen.getByRole('button', { name: 'Check' }));
    expect(await screen.findByText('Location confirmed')).toBeInTheDocument();

    const photo = new File(['photo'], 'issue.jpg', { type: 'image/jpeg' });
    await user.upload(screen.getByLabelText('Photo'), photo);
    await user.click(screen.getByRole('button', { name: /Submit report/ }));

    expect(await screen.findByText('Thank you for speaking up.')).toBeInTheDocument();
    expect(screen.getByText('BG-100099')).toBeInTheDocument();
    expect(screen.getByText('XYZ789')).toBeInTheDocument();
  });
});

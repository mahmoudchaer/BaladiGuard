import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { NotificationLinkPage } from '@/pages/NotificationLinkPage';

vi.mock('@/auth/CitizenAuthContext', () => ({
  useCitizenAuth: () => ({
    isAuthenticated: false,
    isLoading: false,
    profile: null,
  }),
}));

function renderLink(code: string) {
  return render(
    <MemoryRouter initialEntries={[`/t/${code}`]}>
      <Routes>
        <Route path="t/:code" element={<NotificationLinkPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('NotificationLinkPage', () => {
  it('normalizes a valid guest code and never uses ownership language', () => {
    renderLink('abc234');
    expect(screen.getByTestId('notification-link-guest')).toBeInTheDocument();
    expect(screen.getByText(/ABC234/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Track with this code' })).toHaveAttribute(
      'href',
      '/track?trackingCode=ABC234',
    );
    expect(document.body.textContent?.toLowerCase()).not.toMatch(
      /not yours|does not belong|not your report/,
    );
  });

  it('rejects codes outside the tracking alphabet', () => {
    renderLink('IO01AB');
    expect(screen.getByTestId('notification-link-invalid')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Track a report' })).toHaveAttribute('href', '/track');
  });
});

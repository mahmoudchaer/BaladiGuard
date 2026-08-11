import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AppRoutes } from '@/App';
import type { PublicTicketResponse } from '@/types/ticket';

const sample: PublicTicketResponse = {
  ticketNumber: 'BG-100001',
  status: 'IN_PROGRESS',
  category: 'road_damage',
  description: 'Large pothole near campus gate.',
  location: { addressText: 'Near AUB Main Gate, Beirut' },
  mapLocation: {
    addressText: 'Near AUB Main Gate, Beirut',
    latitude: 33.9,
    longitude: 35.482,
  },
  department: { name: 'Roads' },
  attribution: { displayName: 'Community member', isNamed: false },
  photoUrl: null,
  createdAt: '2026-08-01T10:00:00Z',
  updatedAt: '2026-08-02T12:00:00Z',
};

vi.mock('@/services/tickets', async () => {
  const actual = await vi.importActual<typeof import('@/services/tickets')>('@/services/tickets');
  return {
    ...actual,
    getPublicTickets: vi.fn(),
    getPublicTicketByNumber: vi.fn(),
    getTicketByTrackingCode: vi.fn(),
  };
});

vi.mock('@/components/PublicReportsMap', () => ({
  PublicReportsMap: ({ reports }: { reports: PublicTicketResponse[] }) => (
    <div data-testid="public-map">Map with {reports.length} reports</div>
  ),
}));

import {
  getPublicTicketByNumber,
  getPublicTickets,
  getTicketByTrackingCode,
} from '@/services/tickets';

function renderApp(path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe('citizen web public browsing', () => {
  beforeEach(() => {
    vi.mocked(getPublicTickets).mockResolvedValue({
      items: [sample],
      nextCursor: 'next-1',
      limit: 20,
    });
    vi.mocked(getPublicTicketByNumber).mockResolvedValue(sample);
    vi.mocked(getTicketByTrackingCode).mockResolvedValue({
      ticketNumber: 'BG-100001',
      trackingCode: 'ABC234',
      status: 'IN_PROGRESS',
      category: 'road_damage',
      location: { addressText: 'Near AUB Main Gate, Beirut' },
      department: { name: 'Roads' },
      createdAt: '2026-08-01T10:00:00Z',
      updatedAt: '2026-08-02T12:00:00Z',
      lastUpdatedAt: '2026-08-02T12:00:00Z',
      timeline: [{ status: 'SUBMITTED', changedAt: '2026-08-01T10:00:00Z' }],
    });
  });

  it('renders responsive navigation and public list with pagination', async () => {
    const user = userEvent.setup();
    renderApp('/');

    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument();
    expect(await screen.findByTestId('public-report-list')).toBeInTheDocument();
    expect(screen.getByText('BG-100001')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Load more' }));
    await waitFor(() => {
      expect(getPublicTickets).toHaveBeenCalledWith(expect.objectContaining({ cursor: 'next-1' }));
    });
  });

  it('opens public detail from the list', async () => {
    const user = userEvent.setup();
    renderApp('/');
    await user.click(await screen.findByRole('link', { name: /BG-100001/i }));
    expect(await screen.findByTestId('public-detail')).toBeInTheDocument();
    expect(getPublicTicketByNumber).toHaveBeenCalledWith('BG-100001');
  });

  it('shows map with list alternative', async () => {
    renderApp('/map');
    expect(await screen.findByTestId('public-map')).toHaveTextContent('Map with 1 reports');
    expect(screen.getByRole('link', { name: 'View as list' })).toHaveAttribute('href', '/');
  });

  it('tracks by code with fixed wording paths', async () => {
    const user = userEvent.setup();
    renderApp('/track');
    await user.type(screen.getByLabelText('Tracking code'), 'ABC234');
    await user.click(screen.getByRole('button', { name: 'Look up' }));
    expect(await screen.findByTestId('track-result')).toBeInTheDocument();
    expect(screen.getByText(/Tracking code: ABC234/)).toBeInTheDocument();
  });

  it('exposes privacy copy and stub protected routes', async () => {
    const { cleanup } = await import('@testing-library/react');
    renderApp('/privacy');
    expect(await screen.findByRole('heading', { name: 'Privacy' })).toBeInTheDocument();
    expect(screen.getByText(/citizen-safe projection/i)).toBeInTheDocument();
    cleanup();

    renderApp('/login');
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });
});

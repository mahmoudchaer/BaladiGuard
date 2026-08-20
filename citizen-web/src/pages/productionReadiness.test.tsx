import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AppRoutes } from '@/App';
import { t } from '@/i18n';
import type { PublicTicketMapViewportResponse } from '@/types/ticket';

vi.mock('@/components/PublicReportsMap', () => ({
  PublicReportsMap: ({
    data,
    onViewportChange,
  }: {
    data: PublicTicketMapViewportResponse | null;
    onViewportChange: (viewport: {
      north: number;
      south: number;
      east: number;
      west: number;
      zoom: number;
    }) => void;
  }) => (
    <button
      data-testid="public-map"
      onClick={() => onViewportChange({ north: 34, south: 33, east: 36, west: 35, zoom: 15 })}
    >
      Map with {data?.markers.length ?? 0} reports
    </button>
  ),
}));

vi.mock('@/services/tickets', async () => {
  const actual = await vi.importActual<typeof import('@/services/tickets')>('@/services/tickets');
  return {
    ...actual,
    getPublicTickets: vi.fn().mockResolvedValue({ items: [], nextCursor: null, limit: 6 }),
    getPublicMapViewport: vi.fn(),
    getPublicTicketByNumber: vi.fn(),
    getTicketByTrackingCode: vi.fn(),
  };
});

import { getPublicMapViewport, getTicketByTrackingCode } from '@/services/tickets';

function renderApp(path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe('issue #314 production-readiness', () => {
  beforeEach(() => {
    vi.mocked(getPublicMapViewport).mockResolvedValue({
      markers: [],
      clusters: [],
      limit: 200,
      truncated: false,
      zoom: 15,
    });
    vi.mocked(getTicketByTrackingCode).mockResolvedValue({
      ticketNumber: 'BG-100001',
      trackingCode: 'ABC234',
      status: 'IN_PROGRESS',
      category: 'road_damage',
      location: { addressText: 'Hamra' },
      department: { name: 'Roads' },
      createdAt: '2026-08-01T10:00:00Z',
      updatedAt: '2026-08-02T12:00:00Z',
      lastUpdatedAt: '2026-08-02T12:00:00Z',
      timeline: [{ status: 'SUBMITTED', changedAt: '2026-08-01T10:00:00Z' }],
    });
  });

  it('localizes the skip link from catalogs', () => {
    renderApp('/');
    expect(screen.getByRole('link', { name: t('a11y.skipToContent') })).toHaveAttribute(
      'href',
      '#main-content',
    );
  });

  it('sends unknown routes to the public report directory', () => {
    renderApp('/missing-page');
    expect(screen.getByRole('link', { name: t('notFound.browse') })).toHaveAttribute(
      'href',
      '/reports',
    );
  });

  it('keeps explore and tracking reachable from guest chrome', () => {
    renderApp('/');
    expect(screen.getByRole('navigation', { name: t('shell.mainNav') })).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: t('shell.explore') }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: t('shell.trackCode') }).length).toBeGreaterThan(0);
  });

  it('explains tracking before lookup and shows shared status meaning after', async () => {
    const user = userEvent.setup();
    renderApp('/track');
    expect(screen.getByRole('heading', { name: t('track.emptyTitle') })).toBeInTheDocument();
    await user.type(screen.getByLabelText(t('track.codeLabel')), 'ABC234');
    await user.click(screen.getByRole('button', { name: t('common.lookUp') }));
    expect(await screen.findByTestId('track-result')).toBeInTheDocument();
    expect(screen.getByText(t('statusMeaning.IN_PROGRESS'))).toBeInTheDocument();
    expect(screen.getByText(t('nextAction.IN_PROGRESS'))).toBeInTheDocument();
  });

  it('shows a map empty state when the viewport has no published markers', async () => {
    const user = userEvent.setup();
    renderApp('/map');
    await user.click(await screen.findByTestId('public-map'));
    await waitFor(() => {
      expect(screen.getByText(t('public.emptyMap'))).toBeInTheDocument();
    });
  });
});

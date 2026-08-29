import { useEffect } from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useNavigate, type NavigateFunction } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AppRoutes } from '@/App';
import { profileFixture } from '@/contracts/fixtures';
import { t } from '@/i18n';
import { ApiError } from '@/services/api';
import type { PublicTicketMapViewportResponse, PublicTicketResponse } from '@/types/ticket';

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

vi.mock('@/services/citizenAuth', async () => {
  const actual =
    await vi.importActual<typeof import('@/services/citizenAuth')>('@/services/citizenAuth');
  return {
    ...actual,
    getMe: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
  };
});

import { getMe } from '@/services/citizenAuth';
import * as reportDraft from '@/services/reportDraft';
import {
  getPublicMapViewport,
  getPublicTicketByNumber,
  getTicketByTrackingCode,
} from '@/services/tickets';

const publicSample: PublicTicketResponse = {
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

let navigateTo: NavigateFunction;

function NavigateBridge() {
  const navigate = useNavigate();
  useEffect(() => {
    navigateTo = navigate;
  }, [navigate]);
  return null;
}

function renderApp(path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <NavigateBridge />
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe('issue #314 production-readiness', () => {
  afterEach(() => {
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      writable: true,
      value: 1024,
    });
  });

  beforeEach(() => {
    vi.mocked(getMe).mockRejectedValue(
      new ApiError('Unable to restore your session.', 401, 'UNAUTHORIZED'),
    );
    vi.mocked(getPublicTicketByNumber).mockResolvedValue(publicSample);
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

  it('ignores a stale public-detail response after navigation', async () => {
    let resolveOld!: (value: PublicTicketResponse) => void;
    const staleTicket: PublicTicketResponse = {
      ...publicSample,
      ticketNumber: 'BG-OLD001',
      description: 'Stale pothole that must not appear.',
    };
    const currentTicket: PublicTicketResponse = {
      ...publicSample,
      ticketNumber: 'BG-NEW001',
      description: 'Current streetlight report.',
    };
    const oldPending = new Promise<PublicTicketResponse>((resolve) => {
      resolveOld = resolve;
    });

    vi.mocked(getPublicTicketByNumber).mockImplementation((ticketNumber) => {
      if (ticketNumber === 'BG-OLD001') return oldPending;
      return Promise.resolve(currentTicket);
    });

    renderApp('/public/BG-OLD001');
    expect(await screen.findByText(t('public.loadingDetail'))).toBeInTheDocument();

    await act(async () => {
      navigateTo('/public/BG-NEW001');
    });

    expect(await screen.findByTestId('public-detail')).toBeInTheDocument();
    expect(screen.getByText('BG-NEW001')).toBeInTheDocument();
    expect(screen.getByText('Current streetlight report.')).toBeInTheDocument();

    await act(async () => {
      resolveOld(staleTicket);
    });

    expect(screen.queryByText('BG-OLD001')).not.toBeInTheDocument();
    expect(screen.queryByText('Stale pothole that must not appear.')).not.toBeInTheDocument();
    expect(screen.getByText('BG-NEW001')).toBeInTheDocument();
  });

  it('surfaces a clipboard failure after tracking lookup', async () => {
    if (!navigator.clipboard) {
      Object.defineProperty(navigator, 'clipboard', {
        configurable: true,
        value: { writeText: vi.fn() },
      });
    }
    vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValue(new Error('denied'));
    const user = userEvent.setup();
    renderApp('/track');
    await user.type(screen.getByLabelText(t('track.codeLabel')), 'ABC234');
    await user.click(screen.getByRole('button', { name: t('common.lookUp') }));
    expect(await screen.findByTestId('track-result')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: t('track.copyCode') }));
    expect(await screen.findByRole('alert')).toHaveTextContent(t('common.copyFailed'));
  });

  it('blocks submit when the signed-in profile is not contribution-ready', async () => {
    vi.mocked(getMe).mockResolvedValue({ ...profileFixture, contributionReady: false });
    renderApp('/report');
    expect(await screen.findByText(t('report.notContributionReady'))).toBeInTheDocument();
    expect(screen.getByRole('button', { name: new RegExp(t('report.submit')) })).toBeDisabled();
  });

  it('shows a compact menu toggle below 768px', () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, writable: true, value: 375 });
    renderApp('/');
    expect(screen.getByRole('button', { name: t('common.openMenu') })).toBeInTheDocument();
  });

  it('treats the logout draft prompt as a modal that Escape dismisses', async () => {
    vi.mocked(getMe).mockResolvedValue(profileFixture);
    vi.spyOn(reportDraft, 'loadDraft').mockResolvedValue({
      userId: profileFixture.userId,
      description: 'A draft sidewalk report that should prompt on sign-out.',
      addressText: 'Hamra',
      location: null,
      clientSubmissionId: 'sub-draft-1',
      updatedAt: Date.now(),
    });
    const user = userEvent.setup();
    renderApp('/profile');
    expect(await screen.findByRole('heading', { name: t('profile.title') })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: new RegExp(t('profile.signOut')) }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveTextContent(t('profile.keepDraftTitle'));

    await user.keyboard('{Escape}');
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
    expect(screen.getByRole('heading', { name: t('profile.title') })).toBeInTheDocument();
  });
});

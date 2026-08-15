import { act, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AppRoutes } from '@/App';
import { setLocale, t, type AppLocale } from '@/i18n';
import { getTicketByTrackingCode } from '@/services/tickets';

vi.mock('@/services/tickets', async () => {
  const actual = await vi.importActual<typeof import('@/services/tickets')>('@/services/tickets');
  return {
    ...actual,
    getPublicTickets: vi.fn().mockResolvedValue({ items: [], nextCursor: null, limit: 6 }),
    getPublicMapViewport: vi.fn().mockResolvedValue({
      markers: [],
      clusters: [],
      limit: 200,
      truncated: false,
      zoom: 12,
    }),
    getTicketByTrackingCode: vi.fn(),
  };
});

vi.mock('@/components/PublicReportsMap', () => ({
  PublicReportsMap: () => <div data-testid="public-map" />,
}));

const LOCALES: AppLocale[] = ['en', 'ar', 'fr'];

function renderApp(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe('citizen critical-flow localization', () => {
  beforeEach(() => {
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

  it('localizes the report form in Arabic and French', async () => {
    renderApp('/report');
    expect(await screen.findByRole('heading', { name: t('report.title') })).toBeInTheDocument();
    expect(screen.getByLabelText(t('report.describe'))).toBeInTheDocument();
    expect(screen.getByLabelText(t('report.location'))).toBeInTheDocument();

    await act(async () => {
      setLocale('ar');
    });
    expect(screen.getByRole('heading', { name: t('report.title') })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: t('report.submit') })).toBeInTheDocument();
    expect(screen.getByLabelText(t('report.describe'))).toBeInTheDocument();

    await act(async () => {
      setLocale('fr');
    });
    expect(screen.getByRole('heading', { name: t('report.title') })).toBeInTheDocument();
    expect(screen.getByLabelText(t('report.location'))).toBeInTheDocument();
    expect(screen.getByRole('button', { name: t('report.submit') })).toBeInTheDocument();
  });

  it('localizes the OTP login form in all locales', async () => {
    renderApp('/login');
    expect(await screen.findByLabelText(t('auth.phone'))).toBeInTheDocument();

    for (const locale of LOCALES) {
      await act(async () => {
        setLocale(locale);
      });
      expect(screen.getByLabelText(t('auth.phone'))).toBeInTheDocument();
      expect(screen.getByLabelText(t('auth.country'))).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: new RegExp(t('auth.continue')) }),
      ).toBeInTheDocument();
    }
  });

  it('localizes tracking results in Arabic and French', async () => {
    renderApp('/track?trackingCode=ABC234');
    expect(await screen.findByTestId('track-result')).toBeInTheDocument();
    expect(screen.getByText(t('track.timeline'))).toBeInTheDocument();

    await act(async () => {
      setLocale('ar');
    });
    expect(screen.getByText(t('track.timeline'))).toBeInTheDocument();
    expect(screen.getByText(t('track.codeValue', { code: 'ABC234' }))).toBeInTheDocument();

    await act(async () => {
      setLocale('fr');
    });
    expect(screen.getByText(t('track.timeline'))).toBeInTheDocument();
    expect(screen.getByText(t('track.codeValue', { code: 'ABC234' }))).toBeInTheDocument();
  });

  it('keeps language controls and labeled public-browse fields in all locales', async () => {
    renderApp('/reports');
    expect(await screen.findByRole('heading', { name: t('public.title') })).toBeInTheDocument();

    for (const locale of LOCALES) {
      await act(async () => {
        setLocale(locale);
      });
      expect(screen.getByRole('radiogroup', { name: t('a11y.languageGroup') })).toBeInTheDocument();
      expect(screen.getByLabelText(t('public.search'))).toBeInTheDocument();
      expect(screen.getByLabelText(t('public.filterStatus'))).toBeInTheDocument();
      expect(document.documentElement.dir).toBe(locale === 'ar' ? 'rtl' : 'ltr');
    }
  });
});

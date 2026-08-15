import { act, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { setLocale, t, type AppLocale } from '@/i18n';
import { TicketListPage } from '@/pages/TicketListPage';
import { fetchTicketAggregates, fetchTicketsPage } from '@/services/tickets';
import { renderWithProviders } from '@/test/render';

vi.mock('@/services/tickets', async () => {
  const actual = await vi.importActual<typeof import('@/services/tickets')>('@/services/tickets');
  return {
    ...actual,
    fetchTicketsPage: vi.fn(),
    fetchTicketAggregates: vi.fn(),
  };
});

const LOCALES: AppLocale[] = ['en', 'ar', 'fr'];

describe('critical flow accessibility', () => {
  beforeEach(() => {
    vi.mocked(fetchTicketsPage).mockResolvedValue({
      items: [],
      tickets: [],
      nextCursor: null,
      previousCursor: null,
      limit: 25,
      scannedCount: 0,
      approximateTotal: 0,
      freshnessHintSeconds: 30,
      fromCache: false,
    });
    vi.mocked(fetchTicketAggregates).mockResolvedValue({
      openCount: 0,
      criticalCount: 0,
      highCount: 0,
      unassignedCount: 0,
      overdueCount: 0,
      approximate: false,
    });
  });

  it('exposes a language radiogroup and labeled ticket-list controls in en, ar, and fr', async () => {
    renderWithProviders(<TicketListPage />);
    expect(
      await screen.findByRole('heading', { level: 1, name: t('tickets.queueTitle') }),
    ).toBeInTheDocument();

    for (const locale of LOCALES) {
      await act(async () => {
        setLocale(locale);
      });

      expect(screen.getByRole('radiogroup', { name: t('a11y.languageGroup') })).toBeInTheDocument();
      expect(
        screen.getByRole('heading', { level: 1, name: t('tickets.queueTitle') }),
      ).toBeInTheDocument();
      expect(screen.getByLabelText(t('filters.search'))).toBeInTheDocument();
      expect(screen.getByLabelText(t('filters.category'))).toBeInTheDocument();
    }
  });
});

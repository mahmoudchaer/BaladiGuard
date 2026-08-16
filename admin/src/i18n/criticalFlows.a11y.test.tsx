import { act, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { TicketPreviewPanel } from '@/components/TicketPreviewPanel';
import { resetLocaleForTests, setLocale, t, type AppLocale } from '@/i18n';
import { LoginPage } from '@/pages/LoginPage';
import { TicketListPage } from '@/pages/TicketListPage';
import { WorkforcePage } from '@/pages/WorkforcePage';
import {
  assignTicketDepartment,
  fetchTicketAggregates,
  fetchTicketsPage,
  reviewTicketCategory,
  updateTicketStatus,
} from '@/services/tickets';
import { fetchWorkload, listTeams, listWorkers } from '@/services/workforce';
import { renderWithProviders } from '@/test/render';
import type { Ticket } from '@/types/ticket';

vi.mock('@/services/tickets', async () => {
  const actual = await vi.importActual<typeof import('@/services/tickets')>('@/services/tickets');
  return {
    ...actual,
    fetchTicketsPage: vi.fn(),
    fetchTicketAggregates: vi.fn(),
    reviewTicketCategory: vi.fn(),
    updateTicketStatus: vi.fn(),
    assignTicketDepartment: vi.fn(),
  };
});

vi.mock('@/services/workforce', () => ({
  listWorkers: vi.fn(),
  listTeams: vi.fn(),
  fetchWorkload: vi.fn(),
  createWorker: vi.fn(),
  createTeam: vi.fn(),
  updateWorker: vi.fn(),
  updateTeam: vi.fn(),
  setWorkerActive: vi.fn(),
  setTeamActive: vi.fn(),
}));

const LOCALES: AppLocale[] = ['en', 'ar', 'fr'];

const previewTicket: Ticket = {
  ticketId: 'tkt_preview',
  ticketNumber: 'BG-2026-0099',
  trackingCode: 'PREV99',
  description: 'Large pothole near the university gate.',
  contact: {},
  location: {
    latitude: 33.896,
    longitude: 35.478,
    addressText: 'Hamra, Beirut',
    source: 'GPS',
  },
  imageObjectKey: 'reports/road.jpg',
  status: 'SUBMITTED',
  category: 'road_damage',
  priority: 'high',
  createdBy: null,
  municipalityId: null,
  departmentId: null,
  departmentName: undefined,
  duplicateGroupId: null,
  createdAt: '2026-07-17T08:00:00Z',
  updatedAt: '2026-07-17T08:01:00Z',
  ai: {
    aiSuggestedCategory: 'road_damage',
    aiProcessingStatus: 'completed',
  },
};

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
    vi.mocked(listWorkers).mockResolvedValue([]);
    vi.mocked(listTeams).mockResolvedValue([]);
    vi.mocked(fetchWorkload).mockResolvedValue({
      municipalityId: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
      unassigned: { queued: 0, assigned: 0, inProgress: 0, dueSoon: 0, overdue: 0 },
      unassignedTickets: [],
      workers: [],
      teams: [],
    });
    window.localStorage.removeItem('baladiguard.staffSession');
  });

  afterEach(() => {
    resetLocaleForTests();
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
      expect(screen.getByText(t('ticket.preview.selectReport'))).toBeInTheDocument();
    }
  });

  it('exposes labeled login controls in en, ar, and fr', async () => {
    renderWithProviders(<LoginPage />);
    expect(await screen.findByRole('heading', { name: t('login.title') })).toBeInTheDocument();

    for (const locale of LOCALES) {
      await act(async () => {
        setLocale(locale);
      });
      expect(screen.getByRole('radiogroup', { name: t('a11y.languageGroup') })).toBeInTheDocument();
      expect(screen.getByLabelText(t('login.username'))).toBeInTheDocument();
      expect(screen.getByLabelText(t('login.password'))).toBeInTheDocument();
      expect(screen.getByRole('button', { name: t('login.submit') })).toBeInTheDocument();
    }
  });

  it('exposes workforce chrome and language controls in en, ar, and fr', async () => {
    window.localStorage.setItem(
      'baladiguard.staffSession',
      JSON.stringify({
        username: 'admin',
        name: 'Demo Administrator',
        staffId: 'staff_admin_001',
        role: 'administrator',
        municipalityId: null,
        departmentIds: null,
        signedInAt: '2026-08-14T08:00:00Z',
        accessToken: 'test-admin-token',
      }),
    );
    renderWithProviders(<WorkforcePage />);
    expect(await screen.findByRole('heading', { name: t('workforce.title') })).toBeInTheDocument();

    for (const locale of LOCALES) {
      await act(async () => {
        setLocale(locale);
      });
      expect(screen.getByRole('radiogroup', { name: t('a11y.languageGroup') })).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: t('workforce.title') })).toBeInTheDocument();
      expect(screen.getByRole('tablist', { name: t('workforce.viewsA11y') })).toBeInTheDocument();
    }
  });

  it('localizes ticket preview status, category, and department actions in ar/fr', async () => {
    const user = userEvent.setup();
    vi.mocked(reviewTicketCategory).mockResolvedValue({
      ...previewTicket,
      ai: { ...previewTicket.ai, finalCategory: 'waste' },
    });
    vi.mocked(assignTicketDepartment).mockResolvedValue({
      ...previewTicket,
      departmentId: 'd1111111-1111-1111-1111-111111111111',
      departmentName: 'Road Maintenance',
    });

    renderWithProviders(<TicketPreviewPanel ticket={previewTicket} />);
    const preview = screen.getByRole('complementary', { name: t('ticket.preview.a11y') });

    for (const locale of LOCALES) {
      await act(async () => {
        setLocale(locale);
      });
      expect(
        screen.getByRole('complementary', { name: t('ticket.preview.a11y') }),
      ).toBeInTheDocument();
      expect(within(preview).getByText(t('ticket.preview.aiClassification'))).toBeInTheDocument();
      expect(
        within(preview).getByRole('combobox', { name: t('ticket.review.finalCategory') }),
      ).toBeInTheDocument();
      expect(
        within(preview).getByRole('combobox', { name: t('ticket.status') }),
      ).toBeInTheDocument();
      expect(
        within(preview).getByRole('button', { name: t('ticket.review.applyStatus') }),
      ).toBeInTheDocument();
      expect(
        within(preview).getByRole('button', { name: t('ticket.review.saveDepartment') }),
      ).toBeInTheDocument();
    }

    await act(async () => {
      setLocale('ar');
    });
    await user.selectOptions(
      within(preview).getByRole('combobox', { name: t('ticket.review.finalCategory') }),
      'waste',
    );
    await user.click(
      within(preview).getByRole('button', { name: t('ticket.review.saveFinalCategory') }),
    );
    expect(reviewTicketCategory).toHaveBeenCalled();

    await user.selectOptions(
      within(preview).getByRole('combobox', { name: t('ticket.status') }),
      'CLOSED',
    );
    await user.click(within(preview).getByRole('button', { name: t('ticket.review.applyStatus') }));
    expect(screen.getByRole('alert')).toHaveTextContent(
      t('ticket.review.selectReasonBeforeStatus'),
    );

    await act(async () => {
      setLocale('fr');
    });
    expect(screen.getByRole('alert')).toHaveTextContent(
      t('ticket.review.selectReasonBeforeStatus'),
    );
    await user.selectOptions(
      within(preview).getByRole('combobox', {
        name: t('ticket.preview.departmentValue', { department: 'Unassigned' }),
      }),
      'd1111111-1111-1111-1111-111111111111',
    );
    await user.click(
      within(preview).getByRole('button', { name: t('ticket.review.saveDepartment') }),
    );
    expect(assignTicketDepartment).toHaveBeenCalled();
  });
});

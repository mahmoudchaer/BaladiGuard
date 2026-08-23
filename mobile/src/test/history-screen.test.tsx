import React from 'react';
import { act } from 'react-test-renderer';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import HistoryScreen from '../../app/(tabs)/history';
import HomeScreen from '../../app/(tabs)';
import {
  buildCitizenSession,
  loadCitizenSession,
  saveCitizenSession,
} from '@/services/citizenSession';
import { getCitizenMe } from '@/services/api/citizenAuth';
import {
  getPublicTickets,
  getCitizenTicketHistory,
  submitCitizenResolutionFeedback,
  TICKET_HISTORY_UNAUTHORIZED_MESSAGE,
} from '@/services/api/tickets';
import { __getRouterMockState, __resetExpoRouterMock } from '@/test/mocks/expo-router';
import { __resetSecureStoreMock } from '@/test/mocks/expo-secure-store';
import { setLocale, t } from '@/i18n';
import { renderWithProvidersAsync } from '@/test/render';
import type { CitizenProfile } from '@/types/citizen';
import type { CitizenResolutionFeedback, CitizenTicketHistoryResponse } from '@/types/ticket';

vi.mock('@/services/api/citizenAuth', async () => {
  const actual = await vi.importActual<typeof import('@/services/api/citizenAuth')>(
    '@/services/api/citizenAuth',
  );
  return {
    ...actual,
    getCitizenMe: vi.fn(),
  };
});

vi.mock('@/services/api/tickets', async () => {
  const actual =
    await vi.importActual<typeof import('@/services/api/tickets')>('@/services/api/tickets');
  return {
    ...actual,
    getCitizenTicketHistory: vi.fn(),
    submitCitizenResolutionFeedback: vi.fn(),
    getPublicTickets: vi.fn(async () => ({ items: [], nextCursor: null, limit: 20 })),
  };
});

vi.mock('react-native-maps', () => ({
  default: ({ children, ...props }: { children?: React.ReactNode }) =>
    React.createElement('MapView', props, children),
  Marker: ({ children, ...props }: { children?: React.ReactNode }) =>
    React.createElement('Marker', props, children),
}));

const readyProfile: CitizenProfile = {
  userId: 'usr_1',
  phone: '+96170123456',
  phoneVerifiedAt: '2026-08-01T12:00:00Z',
  fullName: 'Ada Citizen',
  email: null,
  notificationPreferences: { ticketUpdates: 'NONE', announcements: false },
  publicNameVisible: false,
  leaderboardOptIn: false,
  active: true,
  contributionReady: true,
  createdAt: '2026-08-01T12:00:00Z',
  updatedAt: '2026-08-01T12:00:00Z',
};

const firstPage: CitizenTicketHistoryResponse = {
  items: [
    {
      trackingCode: 'AB23CD',
      status: 'IN_PROGRESS',
      category: 'road_damage',
      locationAddress: 'Near AUB Main Gate, Hamra, Beirut',
      submittedAt: '2026-07-26T09:00:00Z',
    },
  ],
  nextCursor: '20',
  limit: 20,
};

const secondPage: CitizenTicketHistoryResponse = {
  items: [
    {
      trackingCode: 'CD45EF',
      status: 'SUBMITTED',
      category: null,
      locationAddress: 'Bliss Street, Beirut',
      submittedAt: '2026-07-25T13:15:00Z',
    },
  ],
  nextCursor: null,
  limit: 20,
};

async function seedSession(profile: CitizenProfile = readyProfile) {
  await saveCitizenSession(buildCitizenSession('tok_1', 3600, profile));
  vi.mocked(getCitizenMe).mockResolvedValue(profile);
}

async function flush() {
  for (let i = 0; i < 5; i += 1) {
    await act(async () => {
      await Promise.resolve();
    });
  }
}

function findButton(screen: Awaited<ReturnType<typeof renderWithProvidersAsync>>, text: string) {
  const button = screen.root
    .findAll((node) => String(node.type) === 'Button')
    .find((node) => node.props.children === text);
  if (!button) {
    throw new Error(`Button not found: ${text}`);
  }
  return button;
}

describe('HistoryScreen', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getPublicTickets).mockResolvedValue({ items: [], nextCursor: null, limit: 20 });
    __resetExpoRouterMock();
    __resetSecureStoreMock();
    vi.mocked(getCitizenMe).mockReset();
    vi.mocked(getCitizenTicketHistory).mockReset();
    vi.mocked(submitCitizenResolutionFeedback).mockReset();
  });

  it('shows the history entry point on the signed-in home screen', async () => {
    await seedSession();

    const screen = await renderWithProvidersAsync(<HomeScreen />);

    expect(screen.root.findByProps({ children: 'Your reports' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'View all' })).toBeTruthy();
  });

  it('redirects guests to login with returnTo=/history', async () => {
    await renderWithProvidersAsync(<HistoryScreen />);

    expect(__getRouterMockState().replaceCalls).toContain('/login?returnTo=%2Fhistory');
  });

  it('loads report history and opens the existing tracking detail flow', async () => {
    await seedSession();
    vi.mocked(getCitizenTicketHistory).mockResolvedValue(firstPage);

    const screen = await renderWithProvidersAsync(<HistoryScreen />);
    await flush();

    expect(getCitizenTicketHistory).toHaveBeenCalledWith({
      accessToken: 'tok_1',
      limit: 20,
      cursor: null,
    });
    expect(screen.root.findByProps({ children: 'AB23CD' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Near AUB Main Gate, Hamra, Beirut' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'In Progress' })).toBeTruthy();

    await act(async () => {
      screen.root.findByProps({ testID: 'history-open-AB23CD' }).props.onPress();
    });

    expect(__getRouterMockState().pushCalls).toContainEqual({
      pathname: '/track',
      params: { trackingCode: 'AB23CD' },
    });
  });

  it('shows a loading state while report history is being fetched', async () => {
    await seedSession();
    let resolveHistory: (value: CitizenTicketHistoryResponse) => void = () => undefined;
    vi.mocked(getCitizenTicketHistory).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveHistory = resolve;
        }),
    );

    const screen = await renderWithProvidersAsync(<HistoryScreen />);
    await flush();

    expect(screen.root.findByProps({ testID: 'history-loading' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Loading your reports...' })).toBeTruthy();

    await act(async () => {
      resolveHistory({ items: [], nextCursor: null, limit: 20 });
    });
    await flush();

    expect(screen.root.findByProps({ testID: 'history-empty' })).toBeTruthy();
  });

  it('shows an empty state for an authenticated citizen with no reports', async () => {
    await seedSession();
    vi.mocked(getCitizenTicketHistory).mockResolvedValue({
      items: [],
      nextCursor: null,
      limit: 20,
    });

    const screen = await renderWithProvidersAsync(<HistoryScreen />);
    await flush();

    expect(screen.root.findByProps({ testID: 'history-empty' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'No reports yet' })).toBeTruthy();
  });

  it('loads the next page when pagination is available', async () => {
    await seedSession();
    vi.mocked(getCitizenTicketHistory)
      .mockResolvedValueOnce(firstPage)
      .mockResolvedValueOnce(secondPage);

    const screen = await renderWithProvidersAsync(<HistoryScreen />);
    await flush();

    await act(async () => {
      findButton(screen, 'Load more').props.onPress();
    });
    await flush();

    expect(getCitizenTicketHistory).toHaveBeenLastCalledWith({
      accessToken: 'tok_1',
      limit: 20,
      cursor: '20',
    });
    expect(screen.root.findByProps({ children: 'AB23CD' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'CD45EF' })).toBeTruthy();
    expect(() => screen.root.findByProps({ testID: 'history-load-more' })).toThrow();
  });

  it('tracks concurrent feedback submissions per ticket and blocks duplicate requests', async () => {
    await seedSession();
    vi.mocked(getCitizenTicketHistory).mockResolvedValue({
      items: [
        { ...firstPage.items[0], canSubmitResolutionFeedback: true },
        { ...secondPage.items[0], canSubmitResolutionFeedback: true },
      ],
      nextCursor: null,
      limit: 20,
    });
    const pending = new Map<string, (value: CitizenResolutionFeedback) => void>();
    vi.mocked(submitCitizenResolutionFeedback).mockImplementation(
      ({ trackingCode }) =>
        new Promise((resolve) => {
          pending.set(trackingCode, resolve);
        }),
    );

    const screen = await renderWithProvidersAsync(<HistoryScreen />);
    await flush();
    const first = screen.root.findByProps({ testID: 'resolution-feedback-fixed-AB23CD' });
    const second = screen.root.findByProps({ testID: 'resolution-feedback-fixed-CD45EF' });

    await act(async () => {
      first.props.onPress();
      second.props.onPress();
    });
    expect(
      screen.root.findByProps({ testID: 'resolution-feedback-fixed-AB23CD' }).props.disabled,
    ).toBe(true);
    expect(
      screen.root.findByProps({ testID: 'resolution-feedback-fixed-CD45EF' }).props.disabled,
    ).toBe(true);

    await act(async () => {
      first.props.onPress();
      second.props.onPress();
    });
    expect(submitCitizenResolutionFeedback).toHaveBeenCalledTimes(2);

    await act(async () => {
      pending.get('AB23CD')?.({
        trackingCode: 'AB23CD',
        ticketStatus: 'IN_PROGRESS',
        canSubmit: false,
        status: 'CONFIRMED_FIXED',
        submittedAt: '2026-08-23T09:00:00Z',
      });
    });
    await flush();
    expect(
      screen.root.findByProps({ testID: 'resolution-feedback-fixed-CD45EF' }).props.disabled,
    ).toBe(true);
    expect(submitCitizenResolutionFeedback).toHaveBeenCalledTimes(2);

    await act(async () => {
      pending.get('CD45EF')?.({
        trackingCode: 'CD45EF',
        ticketStatus: 'SUBMITTED',
        canSubmit: false,
        status: 'CONFIRMED_FIXED',
        submittedAt: '2026-08-23T09:00:00Z',
      });
    });
    await flush();
  });

  it('surfaces load errors without clearing the saved session', async () => {
    await seedSession();
    vi.mocked(getCitizenTicketHistory).mockRejectedValue(
      new Error(
        'Unable to load your report history right now. Check your connection and try again.',
      ),
    );

    const screen = await renderWithProvidersAsync(<HistoryScreen />);
    await flush();

    expect(screen.root.findByProps({ testID: 'history-error' })).toBeTruthy();
    await expect(loadCitizenSession()).resolves.not.toBeNull();
  });

  it('switches the history route chrome into Arabic and French', async () => {
    await seedSession();
    vi.mocked(getCitizenTicketHistory).mockResolvedValue(firstPage);

    const screen = await renderWithProvidersAsync(<HistoryScreen />);
    await flush();
    expect(screen.root.findByProps({ children: 'My Reports' })).toBeTruthy();

    await act(async () => {
      setLocale('ar');
    });
    await flush();
    expect(screen.root.findByProps({ children: t('history.title') })).toBeTruthy();
    expect(screen.root.findByProps({ children: t('history.subtitle') })).toBeTruthy();
    expect(screen.root.findByProps({ children: t('status.IN_PROGRESS') })).toBeTruthy();

    await act(async () => {
      setLocale('fr');
    });
    await flush();
    expect(screen.root.findByProps({ children: t('history.title') })).toBeTruthy();
    expect(screen.root.findByProps({ children: t('history.loadMore') })).toBeTruthy();
  });

  it('clears an expired or revoked session after an unauthorized history response', async () => {
    await seedSession();
    vi.mocked(getCitizenTicketHistory).mockRejectedValue(
      new Error(TICKET_HISTORY_UNAUTHORIZED_MESSAGE),
    );

    const screen = await renderWithProvidersAsync(<HistoryScreen />);
    await flush();

    await expect(loadCitizenSession()).resolves.toBeNull();
    expect(__getRouterMockState().replaceCalls).toContain('/login?returnTo=%2Fhistory');
  });
});

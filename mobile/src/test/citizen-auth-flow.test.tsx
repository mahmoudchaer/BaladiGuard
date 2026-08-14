import React from 'react';
import { act } from 'react-test-renderer';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import LoginScreen from '../../app/login/index';
import HomeScreen from '../../app/(tabs)';
import TrackScreen from '../../app/track/index';
import ReportScreen from '../../app/report/index';
import { renderWithProviders, renderWithProvidersAsync } from '@/test/render';
import {
  __getRouterMockState,
  __resetExpoRouterMock,
  __setSearchParams,
} from '@/test/mocks/expo-router';
import { __resetSecureStoreMock } from '@/test/mocks/expo-secure-store';
import { saveCitizenSession, buildCitizenSession } from '@/services/citizenSession';
import type { CitizenProfile } from '@/types/citizen';

vi.mock('@/services/api/citizenAuth', async () => {
  const actual = await vi.importActual<typeof import('@/services/api/citizenAuth')>(
    '@/services/api/citizenAuth',
  );
  return {
    ...actual,
    requestCitizenOtp: vi.fn(),
    verifyCitizenOtp: vi.fn(),
    logoutCitizen: vi.fn(async () => undefined),
    getCitizenMe: vi.fn(),
    updateCitizenProfile: vi.fn(),
  };
});

vi.mock('@/features/citizen-report/ReportForm', () => ({
  ReportForm: () => React.createElement('ReportForm', { testID: 'report-form' }),
}));

vi.mock('@/features/ticket-tracking/TrackLookupForm', () => ({
  TrackLookupForm: () => React.createElement('TrackLookupForm', { testID: 'track-lookup-form' }),
}));

vi.mock('@/services/api/tickets', () => ({
  getPublicTickets: vi.fn(async () => ({
    items: [],
    nextCursor: null,
    limit: 20,
  })),
  getCitizenTicketHistory: vi.fn(),
}));

vi.mock('react-native-maps', () => ({
  default: ({ children, ...props }: { children?: React.ReactNode }) =>
    React.createElement('MapView', props, children),
  Marker: ({ children, ...props }: { children?: React.ReactNode }) =>
    React.createElement('Marker', props, children),
}));

import {
  getCitizenMe,
  logoutCitizen,
  requestCitizenOtp,
  updateCitizenProfile,
  verifyCitizenOtp,
} from '@/services/api/citizenAuth';
import { getCitizenTicketHistory } from '@/services/api/tickets';

const readyProfile: CitizenProfile = {
  userId: 'usr_1',
  phone: '+96170123456',
  phoneVerifiedAt: '2026-08-01T12:00:00Z',
  fullName: 'Ada Citizen',
  email: null,
  notificationPreferences: { ticketUpdates: 'NONE', announcements: false },
  publicNameVisible: false,
  active: true,
  contributionReady: true,
  createdAt: '2026-08-01T12:00:00Z',
  updatedAt: '2026-08-01T12:00:00Z',
};

const phoneOnlyProfile: CitizenProfile = {
  ...readyProfile,
  fullName: null,
  contributionReady: true,
};

function findByTestId(screen: ReturnType<typeof renderWithProviders>, testID: string) {
  return screen.root.findByProps({ testID });
}

function findButton(screen: ReturnType<typeof renderWithProviders>, text: string) {
  const button = screen.root
    .findAll((node) => String(node.type) === 'Button')
    .find((node) => node.props.children === text);
  if (!button) {
    throw new Error(`Button not found: ${text}`);
  }
  return button;
}

describe('citizen auth flows', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    __resetExpoRouterMock();
    __resetSecureStoreMock();
    vi.mocked(getCitizenMe).mockReset();
    vi.mocked(verifyCitizenOtp).mockReset();
    vi.mocked(requestCitizenOtp).mockReset();
    vi.mocked(updateCitizenProfile).mockReset();
    vi.mocked(logoutCitizen).mockReset();
    vi.mocked(getCitizenTicketHistory).mockReset();
  });

  it('keeps public track browsing available without auth', async () => {
    const screen = await renderWithProvidersAsync(<TrackScreen />);
    expect(findByTestId(screen, 'track-lookup-form')).toBeTruthy();
    expect(__getRouterMockState().replaceCalls).toHaveLength(0);
  });

  it('redirects report contributions to login with returnTo when not contribution-ready', async () => {
    await renderWithProvidersAsync(<ReportScreen />);
    expect(__getRouterMockState().replaceCalls).toContain('/login?returnTo=%2Freport');
  });

  it('allows report when a contribution-ready session is restored', async () => {
    await saveCitizenSession(buildCitizenSession('tok_1', 3600, readyProfile));
    vi.mocked(getCitizenMe).mockResolvedValue(readyProfile);

    const screen = await renderWithProvidersAsync(<ReportScreen />);
    expect(findByTestId(screen, 'report-form')).toBeTruthy();
    expect(__getRouterMockState().replaceCalls).toHaveLength(0);
  });

  it('restores a session directly into the signed-in home', async () => {
    await saveCitizenSession(buildCitizenSession('tok_1', 3600, readyProfile));
    vi.mocked(getCitizenMe).mockResolvedValue(readyProfile);
    vi.mocked(logoutCitizen).mockResolvedValue(undefined);
    vi.mocked(getCitizenTicketHistory).mockResolvedValue({
      items: [],
      nextCursor: null,
      limit: 3,
    });

    const screen = await renderWithProvidersAsync(<HomeScreen />);
    expect(screen.root.findByProps({ testID: 'signed-in-home' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Hello, Ada' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Report an issue' })).toBeTruthy();
    expect(screen.root.findByProps({ testID: 'home-summary-empty' })).toBeTruthy();
  });

  it('keeps the signed-in home usable when report updates are offline', async () => {
    await saveCitizenSession(buildCitizenSession('tok_1', 3600, readyProfile));
    vi.mocked(getCitizenMe).mockResolvedValue(readyProfile);
    vi.mocked(getCitizenTicketHistory).mockRejectedValue(new Error('Network unavailable'));

    const screen = await renderWithProvidersAsync(<HomeScreen />);
    expect(screen.root.findByProps({ testID: 'home-summary-error' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Report an issue' })).toBeTruthy();
  });

  it('returns to the intended screen after successful verification', async () => {
    __setSearchParams({ returnTo: '/report' });
    vi.mocked(requestCitizenOtp).mockResolvedValue({
      challengeId: 'ch_1',
      expiresIn: 300,
      message: 'sent',
    });
    vi.mocked(verifyCitizenOtp).mockResolvedValue({
      accessToken: 'tok_1',
      tokenType: 'Bearer',
      expiresIn: 2592000,
      ...readyProfile,
    });

    const screen = await renderWithProvidersAsync(<LoginScreen />);

    await act(async () => {
      findByTestId(screen, 'phone-input').props.onChangeText('+96170123456');
    });
    await act(async () => {
      findButton(screen, 'Send verification code').props.onPress();
    });
    await act(async () => {
      findByTestId(screen, 'otp-code-input').props.onChangeText('123456');
    });
    await act(async () => {
      findButton(screen, 'Verify code').props.onPress();
    });

    expect(__getRouterMockState().replaceCalls).toContain('/report');
  });

  it('returns after phone-only OTP without collecting a name', async () => {
    __setSearchParams({ returnTo: '/report' });
    vi.mocked(requestCitizenOtp).mockResolvedValue({
      challengeId: 'ch_1',
      expiresIn: 300,
      message: 'sent',
    });
    vi.mocked(verifyCitizenOtp).mockResolvedValue({
      accessToken: 'tok_1',
      tokenType: 'Bearer',
      expiresIn: 2592000,
      ...phoneOnlyProfile,
    });

    const screen = await renderWithProvidersAsync(<LoginScreen />);

    await act(async () => {
      findByTestId(screen, 'phone-input').props.onChangeText('+96170123456');
    });
    await act(async () => {
      findButton(screen, 'Send verification code').props.onPress();
    });
    await act(async () => {
      findByTestId(screen, 'otp-code-input').props.onChangeText('123456');
    });
    await act(async () => {
      findButton(screen, 'Verify code').props.onPress();
    });

    expect(() => findByTestId(screen, 'full-name-input')).toThrow();
    expect(updateCitizenProfile).not.toHaveBeenCalled();
    expect(__getRouterMockState().replaceCalls).toContain('/report');
  });

  it('migrates a cached pre-#270 phone-only session when profile refresh is offline', async () => {
    const legacySession = {
      accessToken: 'tok_legacy',
      expiresAt: Date.now() + 3_600_000,
      profile: { ...phoneOnlyProfile, contributionReady: false },
    };
    const { CITIZEN_SESSION_STORAGE_KEY } = await import('@/services/citizenSession');
    const { __getSecureStoreMock } = await import('@/test/mocks/expo-secure-store');
    __getSecureStoreMock().set(CITIZEN_SESSION_STORAGE_KEY, JSON.stringify(legacySession));
    vi.mocked(getCitizenMe).mockRejectedValue(new Error('Network unavailable'));

    const screen = await renderWithProvidersAsync(<ReportScreen />);
    expect(findByTestId(screen, 'report-form')).toBeTruthy();
    expect(__getRouterMockState().replaceCalls).toHaveLength(0);
  });

  it('shows a sign-in path on home for guests', async () => {
    const screen = await renderWithProvidersAsync(<HomeScreen />);
    expect(screen.root.findByProps({ children: 'Sign in or create an account' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Continue as guest' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Track with a code' })).toBeTruthy();
  });
});

import React from 'react';
import { Text } from 'react-native';
import { describe, expect, it, vi } from 'vitest';

import { RequireContributionReady } from '@/auth/RequireContributionReady';
import { renderWithProviders } from '@/test/render';
import type { CitizenProfile } from '@/types/citizen';

const profile: CitizenProfile = {
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
  legalAcceptanceRequired: false,
  createdAt: '2026-08-01T12:00:00Z',
  updatedAt: '2026-08-01T12:00:00Z',
};

const authState = {
  isLoading: false,
  isAuthenticated: true,
  contributionReady: true,
  profile,
  accessToken: 'tok',
  refreshProfile: vi.fn(),
  logout: vi.fn(),
};

vi.mock('@/auth', async () => {
  const actual = await vi.importActual<typeof import('@/auth')>('@/auth');
  return {
    ...actual,
    useCitizenAuth: () => authState,
  };
});

describe('RequireContributionReady', () => {
  it('renders children when the session can contribute', () => {
    Object.assign(authState, {
      isLoading: false,
      isAuthenticated: true,
      contributionReady: true,
      profile: { ...profile, legalAcceptanceRequired: false },
    });
    const screen = renderWithProviders(
      <RequireContributionReady returnTo="/report">
        <Text testID="ready-child">ready</Text>
      </RequireContributionReady>,
    );
    expect(screen.root.findByProps({ testID: 'ready-child' })).toBeTruthy();
  });

  it('keeps an inactive session on a blocked screen instead of login', () => {
    Object.assign(authState, {
      isLoading: false,
      isAuthenticated: true,
      contributionReady: false,
      profile: { ...profile, active: false, contributionReady: false },
    });
    const screen = renderWithProviders(
      <RequireContributionReady returnTo="/report">
        <Text testID="ready-child">ready</Text>
      </RequireContributionReady>,
    );
    expect(screen.root.findByProps({ testID: 'account-blocked' })).toBeTruthy();
    expect(() => screen.root.findByProps({ testID: 'ready-child' })).toThrow();
  });

  it('blocks report entry until updated legal terms are accepted', () => {
    Object.assign(authState, {
      isLoading: false,
      isAuthenticated: true,
      contributionReady: true,
      profile: { ...profile, legalAcceptanceRequired: true },
    });
    const screen = renderWithProviders(
      <RequireContributionReady returnTo="/report">
        <Text testID="ready-child">ready</Text>
      </RequireContributionReady>,
    );
    expect(screen.root.findByProps({ testID: 'legal-acceptance-gate' })).toBeTruthy();
    expect(() => screen.root.findByProps({ testID: 'ready-child' })).toThrow();
  });
});

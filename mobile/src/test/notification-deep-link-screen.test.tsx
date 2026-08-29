import React from 'react';
import { act } from 'react-test-renderer';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import NotificationTicketDeepLinkScreen from '../../app/t/[code]';
import { buildCitizenSession, saveCitizenSession } from '@/services/citizenSession';
import { getCitizenMe } from '@/services/api/citizenAuth';
import {
  __getRouterMockState,
  __resetExpoRouterMock,
  __setSearchParams,
} from '@/test/mocks/expo-router';
import { __resetSecureStoreMock } from '@/test/mocks/expo-secure-store';
import { renderWithProvidersAsync } from '@/test/render';
import type { CitizenProfile } from '@/types/citizen';

vi.mock('@/services/api/citizenAuth', async () => {
  const actual = await vi.importActual<typeof import('@/services/api/citizenAuth')>(
    '@/services/api/citizenAuth',
  );
  return {
    ...actual,
    getCitizenMe: vi.fn(),
  };
});

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

async function seedSession(profile: CitizenProfile = readyProfile) {
  await saveCitizenSession(buildCitizenSession('tok_1', 3600, profile));
  vi.mocked(getCitizenMe).mockResolvedValue(profile);
}

async function flush() {
  for (let i = 0; i < 8; i += 1) {
    await act(async () => {
      await Promise.resolve();
    });
  }
}

function treeContainsUnsafeOwnershipCopy(
  screen: Awaited<ReturnType<typeof renderWithProvidersAsync>>,
) {
  const serialized = JSON.stringify(screen!.toJSON()).toLowerCase();
  // Assert absence of leak-style deny messages (API-style “this is not your ticket”).
  expect(serialized).not.toContain('not yours');
  expect(serialized).not.toContain('does not belong to you');
  expect(serialized).not.toContain('not your report');
}

describe('notification ticket deep-link screen', () => {
  beforeEach(() => {
    __resetExpoRouterMock();
    __resetSecureStoreMock();
    vi.mocked(getCitizenMe).mockReset();
  });

  it('shows safe fallback for malformed codes without ownership language', async () => {
    __setSearchParams({ code: '!!' });
    const screen = await renderWithProvidersAsync(<NotificationTicketDeepLinkScreen />);
    await flush();

    expect(screen.root.findByProps({ children: 'Link cannot be used' })).toBeTruthy();
    expect(screen.root.findByProps({ accessibilityLabel: 'Track a report' })).toBeTruthy();
    treeContainsUnsafeOwnershipCopy(screen);
  });

  it('logged-out offers track and sign-in with returnTo, no ownership leak', async () => {
    __setSearchParams({ code: 'AB23CD' });
    const screen = await renderWithProvidersAsync(<NotificationTicketDeepLinkScreen />);
    await flush();

    expect(screen.root.findByProps({ children: 'Track with this code' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Sign in' })).toBeTruthy();
    expect(JSON.stringify(screen.toJSON())).toContain('AB23CD');
    treeContainsUnsafeOwnershipCopy(screen);

    await act(async () => {
      screen.root.findByProps({ accessibilityLabel: 'Sign in to continue' }).props.onPress();
    });
    const pushes = __getRouterMockState().pushCalls;
    expect(pushes.some((h) => String(h).includes('/login') && String(h).includes('returnTo'))).toBe(
      true,
    );
    expect(String(pushes[0])).toContain('AB23CD');
  });

  it('authenticated users auto-navigate to citizen-safe track for the code', async () => {
    await seedSession();
    __setSearchParams({ code: 'AB23CD' });
    const screen = await renderWithProvidersAsync(<NotificationTicketDeepLinkScreen />);
    await flush();

    treeContainsUnsafeOwnershipCopy(screen);
    const replaces = __getRouterMockState().replaceCalls;
    expect(replaces.some((h) => String(h).includes('/track') && String(h).includes('AB23CD'))).toBe(
      true,
    );
  });
});

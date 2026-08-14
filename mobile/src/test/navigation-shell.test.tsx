import React from 'react';
import { act } from 'react-test-renderer';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CitizenTabsLayout from '../../app/(tabs)/_layout';
import MoreScreen from '../../app/(tabs)/more';
import { buildCitizenSession, saveCitizenSession } from '@/services/citizenSession';
import { __getRouterMockState, __resetExpoRouterMock } from '@/test/mocks/expo-router';
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
    logoutCitizen: vi.fn(async () => undefined),
  };
});

import { getCitizenMe, logoutCitizen } from '@/services/api/citizenAuth';

const profile: CitizenProfile = {
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

async function seedSession() {
  await saveCitizenSession(buildCitizenSession('tok_1', 3600, profile));
  vi.mocked(getCitizenMe).mockResolvedValue(profile);
}

describe('signed-in navigation shell', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    __resetExpoRouterMock();
    __resetSecureStoreMock();
  });

  it('registers the five destinations and opens Report as a focused route', async () => {
    await seedSession();
    const screen = await renderWithProvidersAsync(<CitizenTabsLayout />);
    const tabs = screen.root.findAll((node) => String(node.type) === 'TabsScreen');

    expect(tabs.map((tab) => tab.props.options.title)).toEqual([
      'Home',
      'My Reports',
      'Report',
      'Explore',
      'More',
    ]);

    const reportTab = tabs.find((tab) => tab.props.name === 'report-action');
    const reportButton = reportTab?.props.options.tabBarButton();
    expect(reportButton).toBeTruthy();
    await act(async () => reportButton.props.onPress());
    expect(__getRouterMockState().pushCalls).toContain('/report');
  });

  it('signs out from More and returns to the welcome route', async () => {
    await seedSession();
    const screen = await renderWithProvidersAsync(<MoreScreen />);

    await act(async () => screen.root.findByProps({ testID: 'logout-button' }).props.onPress());

    expect(logoutCitizen).toHaveBeenCalledWith('tok_1');
    expect(__getRouterMockState().replaceCalls).toContain('/');
  });
});

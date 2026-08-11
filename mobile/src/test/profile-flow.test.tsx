import React from 'react';
import { act } from 'react-test-renderer';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import HomeScreen from '../../app/index';
import ProfileScreen from '../../app/profile/index';
import { renderWithProviders, renderWithProvidersAsync } from '@/test/render';
import { __getRouterMockState, __resetExpoRouterMock } from '@/test/mocks/expo-router';
import { __resetSecureStoreMock } from '@/test/mocks/expo-secure-store';
import {
  saveCitizenSession,
  buildCitizenSession,
  loadCitizenSession,
} from '@/services/citizenSession';
import type { CitizenProfile } from '@/types/citizen';
import {
  CitizenAuthApiError,
  PHONE_UNAVAILABLE_MESSAGE,
  PROFILE_UPDATE_SUCCESS_MESSAGE,
} from '@/services/api/citizenAuth';

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

vi.mock('@/services/api/tickets', () => ({
  getPublicTickets: vi.fn(async () => ({ items: [], nextCursor: null, limit: 20 })),
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

async function seedSession(profile: CitizenProfile = readyProfile) {
  await saveCitizenSession(buildCitizenSession('tok_1', 3600, profile));
  vi.mocked(getCitizenMe).mockResolvedValue(profile);
}

describe('citizen profile flows', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    __resetExpoRouterMock();
    __resetSecureStoreMock();
    vi.mocked(getCitizenMe).mockReset();
    vi.mocked(verifyCitizenOtp).mockReset();
    vi.mocked(requestCitizenOtp).mockReset();
    vi.mocked(updateCitizenProfile).mockReset();
    vi.mocked(logoutCitizen).mockReset();
  });

  it('loads the authenticated profile summary', async () => {
    await seedSession();

    const screen = await renderWithProvidersAsync(<ProfileScreen />);
    expect(findByTestId(screen, 'profile-summary')).toBeTruthy();
    expect(findByTestId(screen, 'profile-full-name').props.children).toBe('Ada Citizen');
    expect(findByTestId(screen, 'profile-phone').props.children).toBe('+96170123456');
    expect(findByTestId(screen, 'profile-email').props.children).toBe('Not set');
    expect(findByTestId(screen, 'profile-public-name').props.children).toBe('Hidden (Anonymous)');
    const statusChildren = findByTestId(screen, 'profile-status').props.children;
    const statusText = Array.isArray(statusChildren)
      ? statusChildren.join('')
      : String(statusChildren);
    expect(statusText).toContain('Contribution-ready');
    expect(statusText).toContain('Signed in');
    expect(getCitizenMe).toHaveBeenCalled();
  });

  it('updates profile fields and refreshes the session profile', async () => {
    await seedSession();
    const updated: CitizenProfile = {
      ...readyProfile,
      fullName: 'Ada Updated',
      email: 'ada@example.com',
      notificationPreferences: { ticketUpdates: 'EMAIL', announcements: true },
      publicNameVisible: true,
    };
    vi.mocked(updateCitizenProfile).mockResolvedValue(updated);
    vi.mocked(getCitizenMe).mockResolvedValue(readyProfile);

    const screen = await renderWithProvidersAsync(<ProfileScreen />);

    await act(async () => {
      findByTestId(screen, 'edit-profile-button').props.onPress();
    });

    await act(async () => {
      findByTestId(screen, 'edit-full-name-input').props.onChangeText('Ada Updated');
      findByTestId(screen, 'edit-email-input').props.onChangeText('ada@example.com');
      findByTestId(screen, 'ticket-updates-EMAIL').props.onPress();
      findByTestId(screen, 'edit-announcements-switch').props.onValueChange(true);
      findByTestId(screen, 'edit-public-name-switch').props.onValueChange(true);
    });

    await act(async () => {
      findButton(screen, 'Save changes').props.onPress();
    });

    expect(updateCitizenProfile).toHaveBeenCalledWith(
      'tok_1',
      expect.objectContaining({
        fullName: 'Ada Updated',
        email: 'ada@example.com',
        publicNameVisible: true,
        notificationPreferences: {
          ticketUpdates: 'EMAIL',
          announcements: true,
        },
      }),
    );
    expect(screen.root.findByProps({ children: PROFILE_UPDATE_SUCCESS_MESSAGE })).toBeTruthy();
    expect(findByTestId(screen, 'profile-full-name').props.children).toBe('Ada Updated');
    expect(findByTestId(screen, 'profile-public-name').props.children).toBe(
      'Visible on owned reports',
    );

    const stored = await loadCitizenSession();
    expect(stored?.profile.fullName).toBe('Ada Updated');
    expect(stored?.profile.email).toBe('ada@example.com');
  });

  it('allows nullable non-unique email and explains it is not login recovery', async () => {
    await seedSession({
      ...readyProfile,
      email: 'shared@example.com',
    });
    vi.mocked(updateCitizenProfile).mockResolvedValue({
      ...readyProfile,
      email: null,
    });

    const screen = await renderWithProvidersAsync(<ProfileScreen />);
    expect(findByTestId(screen, 'profile-email').props.children).toBe('shared@example.com');

    await act(async () => {
      findByTestId(screen, 'edit-profile-button').props.onPress();
    });

    expect(findByTestId(screen, 'edit-email-help').props.children).toContain('not used to sign in');

    await act(async () => {
      findByTestId(screen, 'edit-email-input').props.onChangeText('');
    });
    await act(async () => {
      findButton(screen, 'Save changes').props.onPress();
    });

    expect(updateCitizenProfile).toHaveBeenCalledWith(
      'tok_1',
      expect.objectContaining({ email: null }),
    );
  });

  it('changes verified phone through CHANGE_PHONE OTP and refreshes the session', async () => {
    await seedSession();
    vi.mocked(requestCitizenOtp).mockResolvedValue({
      challengeId: 'ch_phone',
      expiresIn: 300,
      message: 'sent',
    });
    const phoneChanged: CitizenProfile = {
      ...readyProfile,
      phone: '+96171999999',
      phoneVerifiedAt: '2026-08-02T12:00:00Z',
    };
    vi.mocked(verifyCitizenOtp).mockResolvedValue({
      accessToken: 'tok_new',
      tokenType: 'Bearer',
      expiresIn: 2592000,
      ...phoneChanged,
    });

    const screen = await renderWithProvidersAsync(<ProfileScreen />);

    await act(async () => {
      findByTestId(screen, 'change-phone-button').props.onPress();
    });
    await act(async () => {
      findByTestId(screen, 'phone-input').props.onChangeText('+96171999999');
    });
    await act(async () => {
      findButton(screen, 'Send verification code').props.onPress();
    });

    expect(requestCitizenOtp).toHaveBeenCalledWith(
      expect.objectContaining({
        phone: '+96171999999',
        purpose: 'CHANGE_PHONE',
      }),
    );

    await act(async () => {
      findByTestId(screen, 'otp-code-input').props.onChangeText('123456');
    });
    await act(async () => {
      findButton(screen, 'Verify code').props.onPress();
    });

    expect(verifyCitizenOtp).toHaveBeenCalledWith({
      challengeId: 'ch_phone',
      code: '123456',
    });
    expect(findByTestId(screen, 'profile-phone').props.children).toBe('+96171999999');

    const stored = await loadCitizenSession();
    expect(stored?.accessToken).toBe('tok_new');
    expect(stored?.profile.phone).toBe('+96171999999');
  });

  it('surfaces duplicate phone rejection without exposing secrets', async () => {
    await seedSession();
    vi.mocked(requestCitizenOtp).mockResolvedValue({
      challengeId: 'ch_busy',
      expiresIn: 300,
      message: 'sent',
    });
    vi.mocked(verifyCitizenOtp).mockRejectedValue(
      new CitizenAuthApiError(PHONE_UNAVAILABLE_MESSAGE, {
        code: 'PHONE_UNAVAILABLE',
        status: 409,
      }),
    );

    const screen = await renderWithProvidersAsync(<ProfileScreen />);

    await act(async () => {
      findByTestId(screen, 'change-phone-button').props.onPress();
    });
    await act(async () => {
      findByTestId(screen, 'phone-input').props.onChangeText('+96171888888');
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

    const tree = JSON.stringify(screen.toJSON());
    expect(tree).toContain(PHONE_UNAVAILABLE_MESSAGE);
    expect(tree).not.toContain('tok_');
    expect(tree).not.toMatch(/"code":"123456"/);
  });

  it('shows rejected profile update errors inline', async () => {
    await seedSession();
    vi.mocked(updateCitizenProfile).mockRejectedValue(
      new CitizenAuthApiError('fullName must be 1–120 characters after trimming.', {
        code: 'VALIDATION_ERROR',
        status: 400,
      }),
    );

    const screen = await renderWithProvidersAsync(<ProfileScreen />);
    await act(async () => {
      findByTestId(screen, 'edit-profile-button').props.onPress();
    });
    await act(async () => {
      findByTestId(screen, 'edit-full-name-input').props.onChangeText('Ada');
    });
    await act(async () => {
      findButton(screen, 'Save changes').props.onPress();
    });

    expect(findByTestId(screen, 'profile-error-banner').props.children).toContain(
      'fullName must be 1–120 characters',
    );
  });

  it('logs out from the profile screen and clears the local session', async () => {
    await seedSession();
    vi.mocked(logoutCitizen).mockResolvedValue(undefined);

    const screen = await renderWithProvidersAsync(<ProfileScreen />);
    await act(async () => {
      findByTestId(screen, 'profile-logout-button').props.onPress();
    });

    expect(logoutCitizen).toHaveBeenCalledWith('tok_1');
    expect(__getRouterMockState().replaceCalls).toContain('/');
    await expect(loadCitizenSession()).resolves.toBeNull();
  });

  it('redirects guests to login with returnTo=/profile', async () => {
    await renderWithProvidersAsync(<ProfileScreen />);
    expect(__getRouterMockState().replaceCalls).toContain('/login?returnTo=%2Fprofile');
  });
});

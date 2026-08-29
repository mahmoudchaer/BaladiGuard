import React from 'react';
import { act } from 'react-test-renderer';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { OtpVerifyForm } from '@/features/citizen-auth/OtpVerifyForm';
import {
  CitizenAuthApiError,
  OTP_EXPIRED_MESSAGE,
  OTP_INVALID_MESSAGE,
  requestCitizenOtp,
  verifyCitizenOtp,
} from '@/services/api/citizenAuth';
import { renderWithProviders } from '@/test/render';

vi.mock('@/services/api/citizenAuth', async () => {
  const actual = await vi.importActual<typeof import('@/services/api/citizenAuth')>(
    '@/services/api/citizenAuth',
  );
  return {
    ...actual,
    requestCitizenOtp: vi.fn(),
    verifyCitizenOtp: vi.fn(),
  };
});

const verifyResponse = {
  accessToken: 'tok_1',
  tokenType: 'Bearer',
  expiresIn: 2592000,
  userId: 'usr_1',
  phone: '+96170123456',
  phoneVerifiedAt: '2026-08-01T12:00:00Z',
  fullName: 'Ada Citizen',
  email: null,
  notificationPreferences: { ticketUpdates: 'NONE' as const, announcements: false },
  publicNameVisible: false,
  leaderboardOptIn: false,
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
    .find((node) => node.props.children === text || String(node.props.children).startsWith(text));
  if (!button) {
    throw new Error(`Button not found: ${text}`);
  }
  return button;
}

describe('OtpVerifyForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('verifies a valid code', async () => {
    vi.mocked(verifyCitizenOtp).mockResolvedValueOnce(verifyResponse);
    const onVerified = vi.fn();
    const screen = renderWithProviders(
      <OtpVerifyForm
        challengeId="ch_1"
        expiresIn={300}
        phone="+96170123456"
        onChallengeReplaced={vi.fn()}
        onVerified={onVerified}
      />,
    );

    await act(async () => {
      findByTestId(screen, 'otp-code-input').props.onChangeText('123456');
    });
    await act(async () => {
      findByTestId(screen, 'accept-legal-checkbox').props.onPress();
    });
    await act(async () => {
      findButton(screen, 'Verify code').props.onPress();
    });

    expect(verifyCitizenOtp).toHaveBeenCalledWith({
      challengeId: 'ch_1',
      code: '123456',
      acceptLegal: true,
      legalLocale: 'en',
    });
    expect(onVerified).toHaveBeenCalledWith(verifyResponse);
  });

  it('shows safe errors for invalid and expired codes', async () => {
    vi.mocked(verifyCitizenOtp).mockRejectedValueOnce(
      new CitizenAuthApiError(OTP_INVALID_MESSAGE, { code: 'INVALID_OTP', status: 400 }),
    );
    const screen = renderWithProviders(
      <OtpVerifyForm
        challengeId="ch_1"
        expiresIn={300}
        phone="+96170123456"
        onChallengeReplaced={vi.fn()}
        onVerified={vi.fn()}
      />,
    );

    await act(async () => {
      findByTestId(screen, 'otp-code-input').props.onChangeText('000000');
    });
    await act(async () => {
      findByTestId(screen, 'accept-legal-checkbox').props.onPress();
    });
    await act(async () => {
      findButton(screen, 'Verify code').props.onPress();
    });
    expect(screen.root.findByProps({ children: OTP_INVALID_MESSAGE })).toBeTruthy();

    vi.mocked(verifyCitizenOtp).mockRejectedValueOnce(
      new CitizenAuthApiError(OTP_EXPIRED_MESSAGE, { code: 'OTP_EXPIRED', status: 400 }),
    );
    await act(async () => {
      findButton(screen, 'Verify code').props.onPress();
    });
    expect(screen.root.findByProps({ children: OTP_EXPIRED_MESSAGE })).toBeTruthy();
  });

  it('resends a code and replaces the challenge', async () => {
    vi.mocked(requestCitizenOtp).mockResolvedValueOnce({
      challengeId: 'ch_2',
      expiresIn: 300,
      message: 'sent',
    });
    const onChallengeReplaced = vi.fn();
    const screen = renderWithProviders(
      <OtpVerifyForm
        challengeId="ch_1"
        expiresIn={300}
        phone="+96170123456"
        region="LB"
        onChallengeReplaced={onChallengeReplaced}
        onVerified={vi.fn()}
      />,
    );

    await act(async () => {
      findButton(screen, 'Resend code').props.onPress();
    });

    expect(requestCitizenOtp).toHaveBeenCalledWith({
      phone: '+96170123456',
      region: 'LB',
      purpose: 'LOGIN_OR_SIGNUP',
    });
    expect(onChallengeReplaced).toHaveBeenCalledWith({
      challengeId: 'ch_2',
      expiresIn: 300,
    });
  });
});

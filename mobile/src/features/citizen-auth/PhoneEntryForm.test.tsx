import React from 'react';
import { act } from 'react-test-renderer';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { PhoneEntryForm } from '@/features/citizen-auth/PhoneEntryForm';
import { CitizenAuthApiError, requestCitizenOtp } from '@/services/api/citizenAuth';
import { renderWithProviders } from '@/test/render';
import { REGION_REQUIRED_MESSAGE } from '@/utils/phone';

vi.mock('@/services/api/citizenAuth', async () => {
  const actual = await vi.importActual<typeof import('@/services/api/citizenAuth')>(
    '@/services/api/citizenAuth',
  );
  return {
    ...actual,
    requestCitizenOtp: vi.fn(),
  };
});

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

describe('PhoneEntryForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows normalized validation errors for national numbers without a region', async () => {
    const onSuccess = vi.fn();
    const screen = renderWithProviders(<PhoneEntryForm onSuccess={onSuccess} />);

    await act(async () => {
      findByTestId(screen, 'phone-region-input').props.onChangeText('');
      findByTestId(screen, 'phone-input').props.onChangeText('70123456');
    });
    await act(async () => {
      findButton(screen, 'Send verification code').props.onPress();
    });

    expect(requestCitizenOtp).not.toHaveBeenCalled();
    expect(screen.root.findByProps({ children: REGION_REQUIRED_MESSAGE })).toBeTruthy();
  });

  it('requests an OTP for a valid phone and region', async () => {
    vi.mocked(requestCitizenOtp).mockResolvedValueOnce({
      challengeId: 'ch_1',
      expiresIn: 300,
      message: 'sent',
    });
    const onSuccess = vi.fn();
    const screen = renderWithProviders(<PhoneEntryForm onSuccess={onSuccess} />);

    await act(async () => {
      findByTestId(screen, 'phone-region-input').props.onChangeText('LB');
      findByTestId(screen, 'phone-input').props.onChangeText('70123456');
    });
    await act(async () => {
      findButton(screen, 'Send verification code').props.onPress();
    });

    expect(requestCitizenOtp).toHaveBeenCalledWith({
      phone: '70123456',
      region: 'LB',
      purpose: 'LOGIN_OR_SIGNUP',
    });
    expect(onSuccess).toHaveBeenCalledWith({
      challengeId: 'ch_1',
      expiresIn: 300,
      phone: '70123456',
      region: 'LB',
    });
  });

  it('surfaces throttling errors safely', async () => {
    vi.mocked(requestCitizenOtp).mockRejectedValueOnce(
      new CitizenAuthApiError('Too many verification requests. Please wait before trying again.', {
        code: 'RATE_LIMITED',
        status: 429,
        retryAfterSeconds: 60,
      }),
    );
    const screen = renderWithProviders(<PhoneEntryForm onSuccess={vi.fn()} />);

    await act(async () => {
      findByTestId(screen, 'phone-input').props.onChangeText('+96170123456');
    });
    await act(async () => {
      findButton(screen, 'Send verification code').props.onPress();
    });

    expect(
      screen.root
        .findAll((node) => String(node.type) === 'Banner')
        .some((node) => JSON.stringify(node.props.children).includes('Too many verification')),
    ).toBe(true);
  });
});

import React from 'react';
import { act } from 'react-test-renderer';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { PhoneEntryForm } from '@/features/citizen-auth/PhoneEntryForm';
import { CitizenAuthApiError, requestCitizenOtp } from '@/services/api/citizenAuth';
import { renderWithProviders } from '@/test/render';

vi.mock('@/services/api/citizenAuth', async () => {
  const actual = await vi.importActual<typeof import('@/services/api/citizenAuth')>(
    '@/services/api/citizenAuth',
  );
  return {
    ...actual,
    requestCitizenOtp: vi.fn(),
  };
});

/** Prefer host nodes (e.g. Pressable) over the composite that forwards testID. */
function findByTestId(screen: ReturnType<typeof renderWithProviders>, testID: string) {
  const hosts = screen.root.findAll(
    (node) =>
      node.props.testID === testID &&
      (typeof node.type === 'string' || typeof node.props.onPress === 'function'),
  );
  if (hosts.length > 0) {
    return hosts[hosts.length - 1]!;
  }
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

  it('defaults the country selector to Lebanon and sends LB with national numbers', async () => {
    vi.mocked(requestCitizenOtp).mockResolvedValueOnce({
      challengeId: 'ch_1',
      expiresIn: 300,
      message: 'sent',
    });
    const onSuccess = vi.fn();
    const screen = renderWithProviders(<PhoneEntryForm onSuccess={onSuccess} />);

    expect(findByTestId(screen, 'country-dialing-selector-value').props.children).toMatch(
      /Lebanon \(\+961\)/i,
    );
    // Free-text ISO region field is gone.
    expect(() => findByTestId(screen, 'phone-region-input')).toThrow();

    await act(async () => {
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

  it('requests an OTP with the selected ISO region after country choice', async () => {
    vi.mocked(requestCitizenOtp).mockResolvedValueOnce({
      challengeId: 'ch_fr',
      expiresIn: 300,
      message: 'sent',
    });
    const onSuccess = vi.fn();
    const screen = renderWithProviders(<PhoneEntryForm onSuccess={onSuccess} />);

    await act(async () => {
      findByTestId(screen, 'country-dialing-selector').props.onPress();
    });
    await act(async () => {
      findByTestId(screen, 'country-dialing-selector-search').props.onChangeText('france');
    });
    await act(async () => {
      findByTestId(screen, 'country-dialing-selector-option-FR').props.onPress();
    });
    await act(async () => {
      findByTestId(screen, 'phone-input').props.onChangeText('612345678');
    });
    await act(async () => {
      findButton(screen, 'Send verification code').props.onPress();
    });

    expect(requestCitizenOtp).toHaveBeenCalledWith({
      phone: '612345678',
      region: 'FR',
      purpose: 'LOGIN_OR_SIGNUP',
    });
    expect(onSuccess).toHaveBeenCalledWith(
      expect.objectContaining({ phone: '612345678', region: 'FR' }),
    );
  });

  it('accepts full E.164 input with the selected country still submitted when present', async () => {
    vi.mocked(requestCitizenOtp).mockResolvedValueOnce({
      challengeId: 'ch_e164',
      expiresIn: 300,
      message: 'sent',
    });
    const screen = renderWithProviders(<PhoneEntryForm onSuccess={vi.fn()} />);

    await act(async () => {
      findByTestId(screen, 'phone-input').props.onChangeText('+96170123456');
    });
    await act(async () => {
      findButton(screen, 'Send verification code').props.onPress();
    });

    expect(requestCitizenOtp).toHaveBeenCalledWith({
      phone: '+96170123456',
      region: 'LB',
      purpose: 'LOGIN_OR_SIGNUP',
    });
  });

  it('explains national-format entry for the selected country', () => {
    const screen = renderWithProviders(<PhoneEntryForm onSuccess={vi.fn()} />);
    expect(String(findByTestId(screen, 'phone-national-helper').props.children)).toMatch(
      /Lebanon/i,
    );
    expect(String(findByTestId(screen, 'phone-national-helper').props.children)).toMatch(/E\.164/i);
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

    const tree = JSON.stringify(screen.toJSON());
    expect(tree).toContain('Too many verification');
    expect(tree).toContain('60');
  });
});

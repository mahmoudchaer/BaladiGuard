import React from 'react';
import { act } from 'react-test-renderer';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ChangePhoneFlow } from '@/features/profile/ChangePhoneFlow';
import { requestCitizenOtp } from '@/services/api/citizenAuth';
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

/** Prefer host nodes over the composite that forwards testID. */
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

describe('ChangePhoneFlow country selector reuse', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('reuses the same country dialing selector and submits ISO region on CHANGE_PHONE', async () => {
    vi.mocked(requestCitizenOtp).mockResolvedValueOnce({
      challengeId: 'ch_change',
      expiresIn: 300,
      message: 'sent',
    });

    const screen = renderWithProviders(
      <ChangePhoneFlow
        currentPhone="+96170123456"
        onVerified={async () => undefined}
        onCancel={() => undefined}
      />,
    );

    expect(findByTestId(screen, 'change-phone-flow')).toBeTruthy();
    expect(findByTestId(screen, 'country-dialing-selector-value').props.children).toMatch(
      /Lebanon \(\+961\)/i,
    );
    expect(() => findByTestId(screen, 'phone-region-input')).toThrow();

    await act(async () => {
      findByTestId(screen, 'country-dialing-selector').props.onPress();
    });
    await act(async () => {
      findByTestId(screen, 'country-dialing-selector-search').props.onChangeText('united states');
    });
    await act(async () => {
      findByTestId(screen, 'country-dialing-selector-option-US').props.onPress();
    });
    await act(async () => {
      findByTestId(screen, 'phone-input').props.onChangeText('2025551234');
    });
    await act(async () => {
      findButton(screen, 'Send verification code').props.onPress();
    });

    expect(requestCitizenOtp).toHaveBeenCalledWith({
      phone: '2025551234',
      region: 'US',
      purpose: 'CHANGE_PHONE',
    });
  });
});

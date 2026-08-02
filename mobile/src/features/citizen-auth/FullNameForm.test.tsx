import React from 'react';
import { act } from 'react-test-renderer';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { FullNameForm } from '@/features/citizen-auth/FullNameForm';
import { renderWithProviders } from '@/test/render';
import { FULL_NAME_REQUIRED_MESSAGE } from '@/schemas/citizenOtpSchema';

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

describe('FullNameForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('requires a full name before continuing', async () => {
    const onSubmitName = vi.fn();
    const screen = renderWithProviders(<FullNameForm onSubmitName={onSubmitName} />);

    await act(async () => {
      findButton(screen, 'Continue').props.onPress();
    });

    expect(onSubmitName).not.toHaveBeenCalled();
    expect(screen.root.findByProps({ children: FULL_NAME_REQUIRED_MESSAGE })).toBeTruthy();
  });

  it('submits a valid first-time full name', async () => {
    const onSubmitName = vi.fn(async () => undefined);
    const screen = renderWithProviders(<FullNameForm onSubmitName={onSubmitName} />);

    await act(async () => {
      findByTestId(screen, 'full-name-input').props.onChangeText('Ada Citizen');
    });
    await act(async () => {
      findButton(screen, 'Continue').props.onPress();
    });

    expect(onSubmitName).toHaveBeenCalledWith('Ada Citizen');
  });
});

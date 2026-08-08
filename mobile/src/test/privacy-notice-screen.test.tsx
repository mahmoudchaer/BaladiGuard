import React from 'react';
import { describe, expect, it } from 'vitest';

import PrivacyNoticeScreen from '../../app/privacy/index';
import { renderWithProviders } from './render';

describe('PrivacyNoticeScreen', () => {
  it('explains collected data and citizen controls', () => {
    const screen = renderWithProviders(<PrivacyNoticeScreen />);

    expect(screen.root.findByProps({ children: 'Privacy notice' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'What we collect' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Your controls' })).toBeTruthy();
    expect(screen.root.findByProps({ testID: 'privacy-policy-url' })).toBeTruthy();
  });
});

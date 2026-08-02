import React from 'react';
import { describe, expect, it } from 'vitest';

import HomeScreen from '../../app/index';
import { renderWithProvidersAsync } from './render';

describe('HomeScreen', () => {
  it('renders the citizen reporting, tracking, and sign-in entry points', async () => {
    const screen = await renderWithProvidersAsync(<HomeScreen />);

    expect(screen.root.findByProps({ children: 'BaladiGuard' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Report an issue' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Track a report' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Sign in with phone' })).toBeTruthy();
  });
});

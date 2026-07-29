import React from 'react';
import { describe, expect, it } from 'vitest';

import HomeScreen from '../../app/index';
import { renderWithProviders } from './render';

describe('HomeScreen', () => {
  it('renders the citizen reporting and tracking entry points', () => {
    const screen = renderWithProviders(<HomeScreen />);

    expect(screen.root.findByProps({ children: 'BaladiGuard' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Report an issue' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Track a report' })).toBeTruthy();
  });
});

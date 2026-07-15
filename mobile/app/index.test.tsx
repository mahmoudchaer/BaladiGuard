import React from 'react';
import { describe, expect, it } from 'vitest';

import HomeScreen from '@/../app/index';
import { renderWithProviders } from '@/test/render';

describe('HomeScreen', () => {
  it('renders the citizen reporting entry point', () => {
    const screen = renderWithProviders(<HomeScreen />);

    expect(screen.root.findByProps({ children: 'BaladiGuard' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Report an issue' })).toBeTruthy();
  });
});

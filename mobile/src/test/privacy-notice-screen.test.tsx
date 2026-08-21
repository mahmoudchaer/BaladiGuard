import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PrivacyNoticeScreen from '../../app/privacy/index';
import { renderWithProviders } from './render';

vi.mock('@/services/api/legal', () => ({
  getLegalDocument: vi.fn(async () => ({
    id: 'privacy',
    title: 'Privacy Policy',
    version: '2026-08-22',
    updatedAt: '2026-08-22T00:00:00Z',
    lang: 'en',
    markdown: '# Privacy Policy\n\nCitizen data handling details.',
  })),
}));

describe('PrivacyNoticeScreen', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('explains public scope and loads the policy', async () => {
    const screen = renderWithProviders(<PrivacyNoticeScreen />);

    expect(screen.root.findByProps({ children: 'Privacy' })).toBeTruthy();
    expect(screen.root.findByProps({ children: 'Public data scope' })).toBeTruthy();
  });
});

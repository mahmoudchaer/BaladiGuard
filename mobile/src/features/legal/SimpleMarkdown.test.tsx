import React from 'react';
import { describe, expect, it } from 'vitest';

import { SimpleMarkdown } from './SimpleMarkdown';
import { renderWithProviders } from '@/test/render';

const PRIVACY_FRAGMENT = `> **Product draft — not a compliance certification.** This document is a product draft.

| Data | Purpose |
| --- | --- |
| Verified phone number | Account identity, login (OTP) |

Account creation requires \`acceptLegal\` on OTP verify.
`;

describe('SimpleMarkdown', () => {
  it('renders GFM tables, blockquotes, and inline code instead of raw markup', () => {
    const screen = renderWithProviders(<SimpleMarkdown markdown={PRIVACY_FRAGMENT} />);

    expect(screen.root.findByProps({ testID: 'legal-blockquote' })).toBeTruthy();
    expect(screen.root.findByProps({ testID: 'legal-table' })).toBeTruthy();
    expect(screen.root.findAllByProps({ children: 'acceptLegal' }).length).toBeGreaterThan(0);
    expect(
      screen.root.findAllByProps({ children: 'Verified phone number' }).length,
    ).toBeGreaterThan(0);
    expect(screen.root.findAllByProps({ children: '> **Product draft' }).length).toBe(0);
    expect(screen.root.findAllByProps({ children: '| Data | Purpose |' }).length).toBe(0);
    expect(screen.root.findAllByProps({ children: '`acceptLegal`' }).length).toBe(0);
  });
});

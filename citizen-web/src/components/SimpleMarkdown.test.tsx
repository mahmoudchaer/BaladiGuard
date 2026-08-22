import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { SimpleMarkdown } from './SimpleMarkdown';

const PRIVACY_FRAGMENT = `> **Product draft — not a compliance certification.** This document is a product draft.

| Data | Purpose |
| --- | --- |
| Verified phone number | Account identity, login (OTP) |
| Legal acceptance record | Evidence that you accepted the current Terms |

Account creation requires acceptance of the current legal package (\`acceptLegal\` on OTP verify).
`;

describe('SimpleMarkdown', () => {
  it('renders GFM tables, blockquotes, and inline code semantically', () => {
    render(<SimpleMarkdown markdown={PRIVACY_FRAGMENT} />);

    expect(screen.getByRole('blockquote')).toHaveTextContent(
      'Product draft — not a compliance certification.',
    );
    expect(screen.queryByText(/^>/)).not.toBeInTheDocument();

    const table = screen.getByRole('table');
    expect(table).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Data' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Purpose' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'Verified phone number' })).toBeInTheDocument();
    expect(screen.queryByText(/\| Data \| Purpose \|/)).not.toBeInTheDocument();

    const code = screen.getByText('acceptLegal');
    expect(code.tagName).toBe('CODE');
    expect(screen.queryByText(/`acceptLegal`/)).not.toBeInTheDocument();
  });
});

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { LocaleProvider } from '@/i18n/LocaleProvider';
import { getLocale } from '@/i18n';

describe('LanguageSwitcher', () => {
  it('switches locale with accessible radio names', async () => {
    const user = userEvent.setup();
    render(
      <LocaleProvider>
        <LanguageSwitcher />
      </LocaleProvider>,
    );

    expect(screen.getByRole('radiogroup')).toBeInTheDocument();
    await user.click(screen.getByTestId('language-option-ar'));
    expect(getLocale()).toBe('ar');
    expect(document.documentElement.dir).toBe('rtl');
    await user.click(screen.getByTestId('language-option-en'));
    expect(getLocale()).toBe('en');
    expect(document.documentElement.dir).toBe('ltr');
  });
});

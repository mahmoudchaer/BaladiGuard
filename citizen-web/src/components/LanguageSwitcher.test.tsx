import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { LocaleProvider } from '@/i18n/LocaleProvider';
import { getLocale } from '@/i18n';

describe('LanguageSwitcher', () => {
  it('shows the current language and switches locale from the dropdown', async () => {
    const user = userEvent.setup();
    render(
      <LocaleProvider>
        <LanguageSwitcher />
      </LocaleProvider>,
    );

    expect(screen.getByTestId('language-menu')).toHaveTextContent('English');
    await user.click(screen.getByTestId('language-menu'));
    expect(screen.getByRole('listbox')).toBeInTheDocument();
    await user.click(screen.getByTestId('language-option-ar'));
    expect(getLocale()).toBe('ar');
    expect(document.documentElement.dir).toBe('rtl');
    expect(screen.getByTestId('language-menu')).toHaveTextContent('العربية');

    await user.click(screen.getByTestId('language-menu'));
    await user.click(screen.getByTestId('language-option-en'));
    expect(getLocale()).toBe('en');
    expect(document.documentElement.dir).toBe('ltr');
    expect(screen.getByTestId('language-menu')).toHaveTextContent('English');
  });
});

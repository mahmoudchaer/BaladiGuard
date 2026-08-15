import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { getLocale, t } from '@/i18n';
import { renderWithProviders } from '@/test/render';

describe('LanguageSwitcher', () => {
  it('persists an allowlisted locale and updates document direction', async () => {
    const user = userEvent.setup();
    renderWithProviders(<LanguageSwitcher />);

    expect(screen.getByRole('radiogroup', { name: t('a11y.languageGroup') })).toBeInTheDocument();

    await user.click(screen.getByRole('radio', { name: t('language.ar') }));
    expect(getLocale()).toBe('ar');
    expect(document.documentElement.dir).toBe('rtl');
    expect(document.documentElement.lang).toBe('ar');
    expect(window.localStorage.getItem('baladiguard.locale')).toBe('ar');

    await user.click(screen.getByTestId('language-option-fr'));
    expect(getLocale()).toBe('fr');
    expect(document.documentElement.dir).toBe('ltr');
    expect(screen.getByTestId('language-option-fr')).toHaveAttribute('aria-checked', 'true');
  });
});

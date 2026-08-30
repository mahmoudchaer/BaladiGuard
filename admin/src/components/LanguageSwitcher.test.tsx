import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { getLocale, t } from '@/i18n';
import { renderWithProviders } from '@/test/render';

describe('LanguageSwitcher', () => {
  it('shows the current language and switches locale from the dropdown', async () => {
    const user = userEvent.setup();
    renderWithProviders(<LanguageSwitcher />);

    const trigger = screen.getByRole('combobox', { name: t('language.en') });
    expect(trigger).toHaveTextContent(t('language.en'));
    await user.click(trigger);
    expect(screen.getByRole('listbox', { name: t('a11y.languageGroup') })).toBeInTheDocument();
    await user.click(screen.getByRole('option', { name: t('language.ar') }));
    expect(getLocale()).toBe('ar');
    expect(document.documentElement.dir).toBe('rtl');
    expect(document.documentElement.lang).toBe('ar');
    expect(window.localStorage.getItem('baladiguard.locale')).toBe('ar');
    expect(screen.getByRole('combobox')).toHaveTextContent(t('language.ar'));
  });

  it('supports keyboard open, escape, select, and focus return', async () => {
    const user = userEvent.setup();
    renderWithProviders(<LanguageSwitcher />);

    const trigger = screen.getByRole('combobox', { name: t('language.en') });
    trigger.focus();
    await user.keyboard('{ArrowDown}');
    expect(screen.getByRole('listbox')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: t('language.en') })).toHaveFocus();

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();

    await user.keyboard('{ArrowDown}');
    await user.keyboard('{ArrowDown}');
    await user.keyboard('{Enter}');
    expect(getLocale()).toBe('ar');
    expect(document.documentElement.dir).toBe('rtl');
    expect(screen.getByRole('combobox')).toHaveFocus();
  });
});

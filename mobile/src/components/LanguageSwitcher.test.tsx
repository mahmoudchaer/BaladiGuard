import { act } from 'react-test-renderer';
import { describe, expect, it } from 'vitest';

import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { getLocale, t } from '@/i18n';
import { renderWithProviders } from '@/test/render';

function findByTestId(root: ReturnType<typeof renderWithProviders>, testID: string) {
  return root.root.findByProps({ testID });
}

describe('LanguageSwitcher', () => {
  it('exposes radio options with accessible names in every locale', async () => {
    const screen = renderWithProviders(<LanguageSwitcher />);

    for (const locale of ['en', 'ar', 'fr'] as const) {
      await act(async () => {
        findByTestId(screen, `language-option-${locale}`).props.onPress();
      });
      expect(getLocale()).toBe(locale);
      expect(findByTestId(screen, 'language-option-en').props.accessibilityRole).toBe('radio');
      expect(findByTestId(screen, 'language-option-ar').props.accessibilityLabel).toBe(
        t('language.ar'),
      );
      expect(findByTestId(screen, 'language-option-en').props.accessibilityState.selected).toBe(
        locale === 'en',
      );
    }
  });
});

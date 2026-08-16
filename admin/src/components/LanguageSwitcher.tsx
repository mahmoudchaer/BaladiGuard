import { SUPPORTED_LOCALES, type AppLocale } from '@/i18n';
import { useI18n } from '@/i18n/LocaleProvider';
import './LanguageSwitcher.css';

type LanguageSwitcherProps = {
  compact?: boolean;
};

export function LanguageSwitcher({ compact = false }: LanguageSwitcherProps) {
  const { locale, t, setLocalePreference } = useI18n();

  return (
    <div
      className={`language-switcher${compact ? ' language-switcher--compact' : ''}`}
      role="radiogroup"
      aria-label={t('a11y.languageGroup')}
    >
      {compact ? null : (
        <>
          <p className="language-switcher__heading">{t('common.language')}</p>
          <p className="language-switcher__hint">{t('language.hint')}</p>
        </>
      )}
      <div className="language-switcher__row">
        {SUPPORTED_LOCALES.map((option) => {
          const selected = option === locale;
          return (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={selected}
              aria-label={t(`language.${option}`)}
              className={`language-switcher__option${
                selected ? ' language-switcher__option--selected' : ''
              }`}
              data-testid={`language-option-${option}`}
              onClick={() => setLocalePreference(option as AppLocale)}
            >
              {t(`language.${option}`)}
            </button>
          );
        })}
      </div>
    </div>
  );
}

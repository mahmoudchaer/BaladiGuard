import { useEffect, useId, useRef, useState } from 'react';
import { SUPPORTED_LOCALES, type AppLocale } from '@/i18n';
import { useI18n } from '@/i18n/LocaleProvider';
import './LanguageSwitcher.css';

type LanguageSwitcherProps = {
  compact?: boolean;
};

export function LanguageSwitcher({ compact = false }: LanguageSwitcherProps) {
  const { locale, t, setLocalePreference } = useI18n();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const listId = useId();

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  const choose = (option: AppLocale) => {
    setLocalePreference(option);
    setOpen(false);
  };

  return (
    <div
      ref={rootRef}
      className={`language-switcher${compact ? ' language-switcher--compact' : ''}${
        open ? ' language-switcher--open' : ''
      }`}
    >
      {compact ? null : (
        <>
          <p className="language-switcher__heading">{t('common.language')}</p>
          <p className="language-switcher__hint">{t('language.hint')}</p>
        </>
      )}
      <div className="language-switcher__control">
        <button
          type="button"
          className="language-switcher__trigger"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-controls={listId}
          aria-label={t('a11y.languageGroup')}
          data-testid="language-menu"
          onClick={() => setOpen((value) => !value)}
        >
          <span>{t(`language.${locale}`)}</span>
          <span className="language-switcher__chevron" aria-hidden>
            ▾
          </span>
        </button>
        {open ? (
          <ul
            id={listId}
            className="language-switcher__menu"
            role="listbox"
            aria-label={t('language.chooser')}
          >
            {SUPPORTED_LOCALES.map((option) => {
              const selected = option === locale;
              return (
                <li key={option} role="presentation">
                  <button
                    type="button"
                    role="option"
                    aria-selected={selected}
                    className={`language-switcher__option${
                      selected ? ' language-switcher__option--selected' : ''
                    }`}
                    data-testid={`language-option-${option}`}
                    onClick={() => choose(option as AppLocale)}
                  >
                    {t(`language.${option}`)}
                  </button>
                </li>
              );
            })}
          </ul>
        ) : null}
      </div>
    </div>
  );
}
